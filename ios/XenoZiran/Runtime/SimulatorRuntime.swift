import Foundation
import os

/// The simulator engine, running in-process on this device (embedded CPython + numpy + the xzr engine package).
///
/// One interpreter per process, started once. Requests and stream polls run on one serial queue, so the page's
/// requests are answered in order; the engine's own worker threads (stepping, comparisons) run alongside.
final class SimulatorRuntime: @unchecked Sendable {
    static let shared = SimulatorRuntime()

    enum State: Equatable { case idle, starting, ready, failed(String) }

    private let queue = DispatchQueue(label: "xzr.runtime", qos: .userInitiated)
    /// Lifecycle commands (pause on backgrounding, memory pressure) must not wait behind interface requests and
    /// stream polls: they run on their own queue (the C layer takes the GIL; the bridge's state is locked).
    private let urgentQueue = DispatchQueue(label: "xzr.runtime.lifecycle", qos: .userInteractive)
    private let log = Logger(subsystem: "io.platodesign.xenoziransimulator", category: "runtime")
    private let lock = NSLock()
    private var _state: State = .idle
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private(set) var startupSeconds: Double = 0

    var state: State { lock.withLock { _state } }

    /// Resource limits of the mobile runtime. Inputs above them are refused with an explicit message naming the
    /// limit (never silently reduced); larger workloads run in the desktop runtime. Measured on the simulator and
    /// documented in docs/ios.md.
    static let mobileLimits: [String: String] = [
        "XZR_MAX_NODES": "3000",
        "XZR_MAX_EDGES": "48000",
        "XZR_MAX_WARMUP": "2000",
        "XZR_MAX_SESSIONS": "2",
        "XZR_MAX_STEP_BATCH": "2000",
        "XZR_MAX_CHECKPOINTS": "12",
        "XZR_MAX_COMPARE_HORIZON": "300",
        "XZR_MAX_ACTIVE_JOBS_PER_SESSION": "1",
        "XZR_MAX_QUEUED_JOBS": "2",
        "XZR_MAX_COMPARES_PER_SESSION": "10",
        "XZR_MAX_JOBS": "40",
        "XZR_MAX_EXPORT_BYTES": "25000000",
        "XZR_MAX_BODY": "8000000",
    ]

    func start() {
        lock.lock()
        guard _state == .idle else { lock.unlock(); return }
        _state = .starting
        lock.unlock()
        queue.async { [self] in
            for (k, v) in Self.mobileLimits { setenv(k, v, 1) }
            setenv("OMP_NUM_THREADS", "1", 1)
            let t0 = Date()
            let resources = Bundle.main.resourcePath ?? ""
            let error: String? = resources.withCString { path in
                guard let e = xzr_python_start(path) else { return nil }
                defer { free(e) }
                return String(cString: e)
            }
            startupSeconds = Date().timeIntervalSince(t0)
            lock.lock()
            if let error {
                _state = .failed(error)
                log.error("runtime failed to start: \(error, privacy: .public)")
            } else {
                _state = .ready
                log.notice("runtime ready in \(self.startupSeconds, privacy: .public) s")
            }
            let w = waiters
            waiters = []
            lock.unlock()
            w.forEach { $0.resume() }
        }
    }

    /// Wait until the runtime has started (or failed to).
    func ready() async {
        await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
            lock.lock()
            if _state == .ready || { if case .failed = _state { return true } else { return false } }() {
                lock.unlock()
                c.resume()
            } else {
                waiters.append(c)
                lock.unlock()
            }
        }
    }

    /// A lifecycle request, served ahead of queued interface work.
    func urgent(_ json: String) async -> String {
        await ready()
        guard state == .ready else { return Self.errorReply(503, "the simulator runtime is not running") }
        return await withCheckedContinuation { c in
            urgentQueue.async {
                let out = json.withCString { req -> String in
                    guard let r = xzr_python_handle(req) else { return Self.errorReply(500, "no reply from the runtime") }
                    defer { free(r) }
                    return String(cString: r)
                }
                c.resume(returning: out)
            }
        }
    }

    /// One bridge request (`{"method","path","body"}` JSON) → response JSON (`{"status","kind","body"}`).
    func request(_ json: String) async -> String {
        await ready()
        if case .failed(let message) = state {
            return Self.errorReply(503, "The simulator runtime could not start on this device: \(message)")
        }
        let queued = Date()
        return await withCheckedContinuation { c in
            queue.async { [log] in
                let started = Date()
                let out = json.withCString { req -> String in
                    guard let r = xzr_python_handle(req) else { return Self.errorReply(500, "no reply from the runtime") }
                    defer { free(r) }
                    return String(cString: r)
                }
                let wait = started.timeIntervalSince(queued), run = Date().timeIntervalSince(started)
                if wait + run > 0.2 {
                    let path = Self.path(of: json)
                    log.notice("slow request \(path, privacy: .public): waited \(wait, privacy: .public) s, ran \(run, privacy: .public) s")
                }
                c.resume(returning: out)
            }
        }
    }

    /// Method and path of a request (for diagnostics; bodies are never logged).
    static func path(of json: String) -> String {
        guard let d = json.data(using: .utf8), let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any]
        else { return "?" }
        return "\(o["method"] ?? "?") \((o["path"] as? String)?.split(separator: "?").first ?? "?")"
    }

    /// Pending stream items (JSON array), or nil while not running.
    func poll() async -> String? {
        guard state == .ready else { return nil }
        return await withCheckedContinuation { c in
            queue.async { [log] in
                let t0 = Date()
                defer {
                    let dt = Date().timeIntervalSince(t0)
                    if dt > 0.1 { log.notice("slow poll: \(dt, privacy: .public) s") }
                }
                guard let r = xzr_python_poll() else { return c.resume(returning: nil) }
                defer { free(r) }
                c.resume(returning: String(cString: r))
            }
        }
    }

    static func errorReply(_ status: Int, _ detail: String) -> String {
        let body: [String: Any] = ["status": status, "kind": "json", "body": ["detail": detail]]
        let data = (try? JSONSerialization.data(withJSONObject: body)) ?? Data()
        return String(data: data, encoding: .utf8) ?? "{}"
    }
}
