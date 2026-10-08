import Foundation
import UniformTypeIdentifiers
import WebKit

/// Serves the bundled web interface (Resources `web/`, built by `npm run build:native`) under `xzr://app/`.
/// Read-only, bundle-confined: paths are resolved inside the web folder and anything that escapes it is refused.
final class BundleSchemeHandler: NSObject, WKURLSchemeHandler {
    static let scheme = "xzr"
    static let host = "app"
    static var startURL: URL { URL(string: "\(scheme)://\(host)/")! }

    private let root: URL

    init(root: URL = Bundle.main.resourceURL!.appendingPathComponent("web", isDirectory: true)) {
        self.root = root.standardizedFileURL
    }

    /// The bundle file for a request URL, or nil when it is not inside the web folder.
    func file(for url: URL) -> URL? {
        guard url.scheme == Self.scheme, url.host == Self.host else { return nil }
        var path = url.path
        if path.isEmpty || path == "/" { path = "/index.html" }
        let candidate = root.appendingPathComponent(String(path.dropFirst())).standardizedFileURL
        guard candidate.path.hasPrefix(root.path + "/") else { return nil }
        return candidate
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url, let file = file(for: url),
              let data = try? Data(contentsOf: file) else {
            let r = HTTPURLResponse(url: task.request.url ?? Self.startURL, statusCode: 404, httpVersion: "HTTP/1.1",
                                    headerFields: ["Content-Type": "text/plain"])!
            task.didReceive(r)
            task.didReceive(Data("not found".utf8))
            task.didFinish()
            return
        }
        let mime = UTType(filenameExtension: file.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
        let r = HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1",
                                headerFields: ["Content-Type": mime, "Content-Length": "\(data.count)",
                                               "Cache-Control": "no-cache"])!
        task.didReceive(r)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}
}
