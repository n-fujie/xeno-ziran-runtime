import WebKit
import XCTest
@testable import XenoZiranSimulator

final class WebHostTests: XCTestCase {
    func testSchemeHandlerServesOnlyTheBundledInterface() throws {
        let h = BundleSchemeHandler()
        XCTAssertNotNil(h.file(for: URL(string: "xzr://app/")!))
        XCTAssertTrue(FileManager.default.fileExists(atPath: h.file(for: URL(string: "xzr://app/")!)!.path),
                      "the bundled interface (web/index.html) is missing")
        XCTAssertNil(h.file(for: URL(string: "xzr://app/../python/lib/python3.14/os.py")!))
        XCTAssertNil(h.file(for: URL(string: "xzr://app/%2E%2E/app/xzr/__init__.py")!))
        XCTAssertNil(h.file(for: URL(string: "xzr://other/index.html")!))
        XCTAssertNil(h.file(for: URL(string: "https://app/index.html")!))
    }

    func testBundledInterfaceIsTheNativeBuildAndLoadsNothingRemote() throws {
        let web = Bundle.main.resourceURL!.appendingPathComponent("web")
        let index = try String(contentsOf: web.appendingPathComponent("index.html"), encoding: .utf8)
        XCTAssertTrue(index.contains("Content-Security-Policy"))
        XCTAssertFalse(index.contains("fonts.googleapis.com"))
        let assets = try FileManager.default.contentsOfDirectory(at: web.appendingPathComponent("assets"),
                                                                 includingPropertiesForKeys: nil)
        for a in assets where a.pathExtension == "css" {
            XCTAssertFalse(try String(contentsOf: a, encoding: .utf8).contains("googleapis"), a.lastPathComponent)
        }
        // the app's bundle contains no networking modules of the interpreter
        let dynload = Bundle.main.resourceURL!.appendingPathComponent("python/lib/python3.14/lib-dynload")
        let names = try FileManager.default.contentsOfDirectory(atPath: dynload.path).joined(separator: " ")
        XCTAssertFalse(names.contains("_socket") || names.contains("_ssl"), names)
    }

    func testPausedIDsParsing() {
        XCTAssertEqual(WebHost.pausedIDs(#"{"status":200,"kind":"json","body":{"paused":["a","b"]}}"#), ["a", "b"])
        XCTAssertEqual(WebHost.pausedIDs("garbage"), [])
    }
}
