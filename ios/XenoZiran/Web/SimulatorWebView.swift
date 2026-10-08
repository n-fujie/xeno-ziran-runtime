import SwiftUI
import UIKit
import WebKit
import os

/// The simulator interface: the bundled web UI in a WKWebView, connected to the in-process runtime.
///
/// The page talks to the runtime only through the `xzr` message handler (request / share / openResults); there is
/// no socket, server or remote origin. Navigation is confined to the bundled `xzr://app/` pages; the only outbound
/// link, the research-results site, opens in the system browser.
struct SimulatorWebView: UIViewRepresentable {
    @ObservedObject var host: WebHost

    func makeUIView(context: Context) -> WKWebView { host.webView }
    func updateUIView(_ view: WKWebView, context: Context) {}
}

@MainActor
final class WebHost: NSObject, ObservableObject, WKNavigationDelegate, WKScriptMessageHandlerWithReply, WKUIDelegate {
    static let resultsSite = URL(string: "https://ziran-xeno-simulator.vercel.app")!
    /// Stream delivery rate: the desktop service pushes at the same order of magnitude.
    static let pollInterval: TimeInterval = 1.0 / 30.0

    let webView: WKWebView
    let runtime: SimulatorRuntime
    @Published var loaded = false
    @Published var pageError: String?

    private let log = Logger(subsystem: "io.platodesign.xenoziransimulator", category: "web")
    private var timer: Timer?
    private var polling = false
    private var active = true

    init(runtime: SimulatorRuntime = .shared) {
        self.runtime = runtime
        let config = WKWebViewConfiguration()
        config.setURLSchemeHandler(BundleSchemeHandler(), forURLScheme: BundleSchemeHandler.scheme)
        config.websiteDataStore = .nonPersistent()  // nothing is stored by the page; saves go through the share sheet
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        config.allowsInlineMediaPlayback = false
        config.dataDetectorTypes = []
        webView = WKWebView(frame: .zero, configuration: config)
        super.init()
        config.userContentController.addScriptMessageHandler(self, contentWorld: .page, name: "xzr")
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.backgroundColor = .black
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.allowsLinkPreview = false
        webView.accessibilityIdentifier = "simulator-web"
        #if DEBUG
        if #available(iOS 16.4, *) { webView.isInspectable = true }
        #endif
        // hosting unit tests: the runtime is exercised directly; the interface (and its default session) stays idle
        if ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil { return }
        webView.load(URLRequest(url: BundleSchemeHandler.startURL))
        startPolling()
    }

    // MARK: stream pump

    func startPolling() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: Self.pollInterval, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.pump() }
        }
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
    }

    private func pump() {
        guard loaded, active, !polling else { return }
        polling = true
        Task {
            defer { polling = false }
            guard let json = await runtime.poll(), json != "[]" else { return }
            _ = try? await webView.evaluateJavaScript("window.__xzrNative && window.__xzrNative.push(\(json)); 0")
        }
    }

    // MARK: lifecycle

    /// The app leaves the foreground: pause every running session before iOS suspends the process. The pause runs
    /// under a background-task assertion so it completes before suspension; returning to the foreground waits for it.
    func enterBackground() {
        guard active else { return }
        log.notice("lifecycle: background — pausing")
        active = false
        stopPolling()
        let assertion = UIApplication.shared.beginBackgroundTask(withName: "xzr.pause")
        pausing = Task { [runtime] in
            let reply = await runtime.urgent(#"{"method":"POST","path":"/native/lifecycle/background","body":null}"#)
            Logger(subsystem: "io.platodesign.xenoziransimulator", category: "web")
                .notice("lifecycle: background — paused \(Self.pausedIDs(reply).count, privacy: .public)")
            if assertion != .invalid { await UIApplication.shared.endBackgroundTask(assertion) }
        }
    }

    private var pausing: Task<Void, Never>?

    func enterForeground() {
        guard !active else { return }
        active = true
        let pending = pausing
        pausing = nil
        Task { [runtime] in
            await pending?.value
            // every session paused because of the background period, including a run that was still in flight
            let reply = await runtime.urgent(#"{"method":"POST","path":"/native/lifecycle/foreground","body":null}"#)
            let paused = Self.pausedIDs(reply)
            log.notice("lifecycle: foreground — paused during background: \(paused.count, privacy: .public)")
            startPolling()
            let detail = (try? JSONSerialization.data(withJSONObject: ["paused": paused]))
                .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
            _ = try? await webView.evaluateJavaScript(
                "window.__xzrNative && window.__xzrNative.lifecycle('foreground', \(detail)); 0")
        }
    }

    func memoryWarning() async {
        let reply = await runtime.urgent(#"{"method":"POST","path":"/native/lifecycle/memory-warning","body":null}"#)
        if !Self.pausedIDs(reply).isEmpty {
            _ = try? await webView.evaluateJavaScript(
                "window.__xzrNative && window.__xzrNative.lifecycle('memory', {}); 0")
        }
    }

    nonisolated static func pausedIDs(_ reply: String) -> [String] {
        guard let d = reply.data(using: .utf8),
              let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let body = o["body"] as? [String: Any] else { return [] }
        return body["paused"] as? [String] ?? []
    }

    // MARK: messages from the page

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                               replyHandler: @escaping @MainActor @Sendable (Any?, String?) -> Void) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.protocol == BundleSchemeHandler.scheme,
              let body = message.body as? [String: Any], let op = body["op"] as? String else {
            replyHandler(nil, "refused")
            return
        }
        switch op {
        case "request":
            guard let request = body["request"] as? String, request.utf8.count <= 16_000_000 else {
                replyHandler(nil, "invalid request")
                return
            }
            Task {
                let reply = await runtime.request(request)
                replyHandler(reply, nil)
            }
        case "share":
            guard let name = body["filename"] as? String, let text = body["text"] as? String else {
                replyHandler(nil, "invalid share")
                return
            }
            share(filename: name, text: text)
            replyHandler(true, nil)
        case "openResults":
            UIApplication.shared.open(Self.resultsSite)
            replyHandler(true, nil)
        default:
            replyHandler(nil, "unknown operation")
        }
    }

    /// Present the share sheet for a file the page produced (Save, exports): Save to Files, AirDrop, …
    func share(filename: String, text: String) {
        let safe = filename.replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "..", with: "_")
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("share", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent(safe.isEmpty ? "xzr-export.txt" : safe)
        do {
            try Data(text.utf8).write(to: url, options: .atomic)
        } catch {
            pageError = "The file could not be prepared: \(error.localizedDescription)"
            return
        }
        let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        guard let presenter = webView.window?.rootViewController?.topMost else { return }
        sheet.popoverPresentationController?.sourceView = webView
        sheet.popoverPresentationController?.sourceRect = CGRect(x: webView.bounds.midX, y: 60, width: 1, height: 1)
        presenter.present(sheet, animated: true)
    }

    // MARK: navigation: bundled pages only

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let url = action.request.url else { return .cancel }
        if url.scheme == BundleSchemeHandler.scheme && url.host == BundleSchemeHandler.host { return .allow }
        if url.scheme == "about" { return .allow }
        if action.navigationType == .linkActivated, url.scheme == "https", url.host == Self.resultsSite.host {
            await UIApplication.shared.open(url)
        }
        log.notice("blocked navigation to \(url.absoluteString, privacy: .public)")
        return .cancel
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        loaded = true
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        pageError = "The simulator interface could not be shown: \(error.localizedDescription)"
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        pageError = "The simulator interface could not be loaded: \(error.localizedDescription)"
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        // the page's process was ended by the system (memory); the runtime and its sessions are intact: reload the
        // interface, which resumes the current session from the runtime
        log.error("web content process terminated; reloading")
        loaded = false
        webView.load(URLRequest(url: BundleSchemeHandler.startURL))
    }

    // window.open / target=_blank: never a new web view
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        nil
    }
}

extension UIViewController {
    var topMost: UIViewController {
        presentedViewController?.topMost ?? self
    }
}
