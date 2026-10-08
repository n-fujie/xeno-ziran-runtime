import CryptoKit
import XCTest
@testable import XenoZiranSimulator

/// The on-device runtime, exercised in-process through the same bridge the interface uses.
final class RuntimeTests: XCTestCase {
    let runtime = SimulatorRuntime.shared

    override func setUp() async throws {
        runtime.start()
        await runtime.ready()
        XCTAssertEqual(runtime.state, .ready, "runtime failed to start: \(runtime.state)")
    }

    struct Reply {
        let status: Int
        let kind: String
        let body: Any
        var json: [String: Any] { body as? [String: Any] ?? [:] }
        var bytes: Data { Data(base64Encoded: body as? String ?? "") ?? Data() }
    }

    func call(_ method: String, _ path: String, _ body: Any? = nil) async throws -> Reply {
        let req: [String: Any] = ["method": method, "path": path, "body": body ?? NSNull()]
        let text = String(data: try JSONSerialization.data(withJSONObject: req), encoding: .utf8)!
        let out = await runtime.request(text)
        let o = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(out.utf8)) as? [String: Any])
        return Reply(status: o["status"] as? Int ?? 0, kind: o["kind"] as? String ?? "", body: o["body"] ?? NSNull())
    }

    func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: "json"))
        return try Data(contentsOf: url)
    }

    func waitFor(_ sid: String, t: Int, timeout: TimeInterval = 120) async throws {
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            let info = try await call("GET", "/api/sessions/\(sid)").json
            if (info["t"] as? Int ?? 0) >= t, (info["pending_steps"] as? Int ?? 0) == 0 { return }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTFail("session did not reach t=\(t)")
    }

    func testHealthReportsTheNativeRuntimeAndItsLimits() async throws {
        let h = try await call("GET", "/api/health")
        XCTAssertEqual(h.status, 200)
        XCTAssertEqual(h.json["native"] as? Bool, true)
        XCTAssertEqual(h.json["max_nodes"] as? Int, 3000)
        let scenarios = try await call("GET", "/api/scenarios")
        let ids = (scenarios.body as? [[String: Any]] ?? []).compactMap { $0["id"] as? String }
        XCTAssertTrue(Set(["small-600", "reason-lab", "demo-3k"]).isSubset(of: Set(ids)), "\(ids)")
    }

    func testOnlyAllowlistedRoutesExist() async throws {
        for (m, p) in [("GET", "/api/experiments"), ("POST", "/api/experiments/run"), ("GET", "/api/ops/metrics"),
                       ("GET", "/etc/passwd"), ("POST", "/native/shell"), ("GET", "/native/eval"),
                       ("GET", "/api/sessions/../../x")] {
            let r = try await call(m, p)
            XCTAssertEqual(r.status, 404, "\(m) \(p)")
        }
        let traversal = try await call("POST", "/api/sessions", ["sample": "../scenarios/demo-3k"])
        XCTAssertEqual(traversal.status, 404)
    }

    func testOversizedWorkloadsAreRefusedExplicitly() async throws {
        let r = try await call("POST", "/api/sessions", ["sample": "benchmark-10k"])
        XCTAssertEqual(r.status, 413)
        XCTAssertEqual(r.json["limit"] as? String, "max_nodes")
        XCTAssertTrue((r.json["error"] as? String ?? "").contains("desktop runtime"))
    }

    func testStepRewindCompareAndStream() async throws {
        let sid = try await call("POST", "/api/sessions", ["sample": "small-600"]).json["id"] as! String
        let stream = try await call("POST", "/native/stream/\(sid)")
        XCTAssertEqual(stream.status, 200)
        let key = stream.json["stream"] as! String
        _ = try await call("POST", "/api/sessions/\(sid)/control", ["action": "step", "steps": 30])
        try await waitFor(sid, t: 30)
        let polled = await runtime.poll() ?? "[]"
        XCTAssertTrue(polled.contains(key) && polled.contains("\"metrics\""), polled.prefix(200).description)
        let tile = try await call("GET", "/api/sessions/\(sid)/tile?layout=network&level=4&x0=0&y0=0&x1=1000&y1=1000")
        XCTAssertEqual(tile.status, 200)
        XCTAssertGreaterThan(tile.bytes.count, 100)
        let job = try await call("POST", "/api/sessions/\(sid)/compare", ["horizon": 20]).json["job"] as! String
        var status = "running"
        for _ in 0..<2000 where status == "running" || status == "queued" {
            status = try await call("GET", "/api/jobs/\(job)").json["status"] as? String ?? "?"
            try await Task.sleep(nanoseconds: 20_000_000)
        }
        XCTAssertEqual(status, "done")
        let cmd = try await call("POST", "/api/sessions/\(sid)/practice/command", ["text": "frobnicate everything"])
        XCTAssertEqual(cmd.status, 400)
        XCTAssertNotNil(cmd.json["suggestions"])
        let closedStream = try await call("DELETE", "/native/stream/\(key)")
        XCTAssertEqual(closedStream.status, 200)
        let closedSession = try await call("DELETE", "/api/sessions/\(sid)")
        XCTAssertEqual(closedSession.status, 200)
    }

    func testBackgroundingPausesRunningSessions() async throws {
        let sid = try await call("POST", "/api/sessions", ["sample": "small-600"]).json["id"] as! String
        _ = try await call("POST", "/api/sessions/\(sid)/control", ["action": "run"])
        let r = try await call("POST", "/native/lifecycle/background")
        XCTAssertEqual(r.json["paused"] as? [String], [sid])
        let t1 = try await call("GET", "/api/sessions/\(sid)").json
        XCTAssertEqual(t1["running"] as? Bool, false)
        try await Task.sleep(nanoseconds: 300_000_000)
        let t2 = try await call("GET", "/api/sessions/\(sid)").json
        XCTAssertEqual(t1["t"] as? Int, t2["t"] as? Int, "nothing runs while paused")
        // a Run still in flight after backgrounding does not start; it is reported on return
        let late = try await call("POST", "/api/sessions/\(sid)/control", ["action": "run"])
        XCTAssertEqual(late.json["running"] as? Bool, false)
        let back = try await call("POST", "/native/lifecycle/foreground")
        XCTAssertEqual(back.json["paused"] as? [String], [sid])
        let again = try await call("POST", "/api/sessions/\(sid)/control", ["action": "run"])
        XCTAssertEqual(again.json["running"] as? Bool, true, "runs may start once the app is active")
        _ = try await call("DELETE", "/api/sessions/\(sid)")
    }

    /// A Save file written by the desktop runtime loads here and produces the identical state, byte for byte.
    func testDesktopSaveFileLoadsToTheIdenticalState() async throws {
        let saved = try XCTUnwrap(try JSONSerialization.jsonObject(with: fixture("desktop_save")) as? [String: Any])
        let expect = try XCTUnwrap(try JSONSerialization.jsonObject(with: fixture("desktop_save_expect")) as? [String: Any])
        let r = try await call("POST", "/api/sessions", ["scenario": saved["scenario"]!, "applied": saved["applied"]!])
        XCTAssertEqual(r.status, 200, "\(r.body)")
        let sid = r.json["id"] as! String
        _ = try await call("POST", "/api/sessions/\(sid)/control", ["action": "step", "steps": expect["steps"] as! Int])
        try await waitFor(sid, t: expect["t"] as! Int)
        try await Task.sleep(nanoseconds: 300_000_000)
        let snap = try await call("GET", "/api/sessions/\(sid)/snapshot").bytes
        let digest = SHA256.hash(data: snap).map { String(format: "%02x", $0) }.joined()
        XCTAssertEqual(digest, expect["snapshot_sha256"] as? String)
        // and this app's own Save round-trips
        let mine = try await call("GET", "/api/sessions/\(sid)/save").json
        let again = try await call("POST", "/api/sessions", ["scenario": mine["scenario"]!, "applied": mine["applied"]!])
        XCTAssertEqual(again.status, 200)
        let resaved = try await call("GET", "/api/sessions/\(again.json["id"] as! String)/save").json
        XCTAssertEqual(NSDictionary(dictionary: resaved["scenario"] as! [String: Any]),
                       NSDictionary(dictionary: mine["scenario"] as! [String: Any]))
    }

    #if DEBUG
    /// The embedded engine against the desktop golden fixture: dynamics bit-identical, observations within tolerance.
    func testEngineConformanceAgainstTheDesktopGoldenFixture() throws {
        let reference = String(data: try fixture("conformance_reference"), encoding: .utf8)!
        let started = Date()
        let raw = reference.withCString { ref -> String in
            let r = xzr_python_conformance(ref)!
            defer { free(r) }
            return String(cString: r)
        }
        let out = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(raw.utf8)) as? [String: Any], raw)
        XCTAssertNil(out["error"], "\(out["error"] ?? "")")
        let comparison = try XCTUnwrap(out["comparison"] as? [String: Any])
        XCTAssertEqual((comparison["exact_differences"] as? [String])?.count, 0, "\(comparison)")
        XCTAssertEqual((comparison["observation_differences"] as? [String])?.count, 0, "\(comparison)")
        let seconds = out["seconds"] ?? [:]
        let line = "CONFORMANCE seconds=\(seconds) total=\(Date().timeIntervalSince(started))"
        print(line)
        add(XCTAttachment(string: line))
    }

    /// Timings on this machine (simulator or device — reported, not asserted beyond sanity).
    func testBenchmark() throws {
        for name in ["small-600", "reason-lab", "demo-3k"] {
            let raw = name.withCString { n -> String in
                let r = xzr_python_benchmark(n)!
                defer { free(r) }
                return String(cString: r)
            }
            print("BENCHMARK \(raw)")
            add(XCTAttachment(string: raw))
            let o = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(raw.utf8)) as? [String: Any], raw)
            XCTAssertNil(o["error"])
            XCTAssertGreaterThan(o["session_steps_per_s"] as? Double ?? 0, 0)
        }
    }
    #endif

    func testStartupTimeIsRecorded() {
        print("STARTUP runtime_seconds=\(runtime.startupSeconds)")
        XCTAssertGreaterThan(runtime.startupSeconds, 0)
    }
}
