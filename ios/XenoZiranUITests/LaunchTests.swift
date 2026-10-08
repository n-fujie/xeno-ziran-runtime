import XCTest

/// The interface end to end: launch, the runtime builds a session, every interactive view opens and renders.
final class LaunchTests: XCTestCase {
    static let views = ["Network", "Shape Space", "Address Space", "World Map", "3D Globe", "Timeline", "Compare",
                         "Philosophical Practice"]

    override func setUp() {
        continueAfterFailure = true
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot())
        a.name = name
        a.lifetime = .keepAlways
        add(a)
    }

    @MainActor
    func testLaunchRunAndOpenEveryView() throws {
        let app = XCUIApplication()
        let t0 = Date()
        app.launch()
        let web = app.webViews.firstMatch
        XCTAssertTrue(web.waitForExistence(timeout: 60))
        let run = web.buttons.matching(NSPredicate(format: "label CONTAINS 'Run'")).firstMatch
        XCTAssertTrue(run.waitForExistence(timeout: 240), "the session did not start")
        print("UI first_session_seconds=\(Date().timeIntervalSince(t0))")
        shot(app, "00-launch")

        run.tap()
        sleep(3)
        shot(app, "01-running")
        let pause = web.buttons.matching(NSPredicate(format: "label CONTAINS 'Pause'")).firstMatch
        XCTAssertTrue(pause.waitForExistence(timeout: 30))
        pause.tap()

        for (i, v) in Self.views.enumerated() {
            let tab = web.buttons[v]
            XCTAssertTrue(tab.waitForExistence(timeout: 10), "tab \(v)")
            for _ in 0..<6 where !tab.isHittable { web.buttons["Network"].swipeLeft() }  // the tab strip scrolls
            tab.tap()
            sleep(v == "World Map" || v == "3D Globe" ? 4 : 2)
            XCTAssertFalse(web.staticTexts.matching(NSPredicate(format: "label CONTAINS 'could not be shown'")).firstMatch.exists,
                           "\(v) failed to render")
            shot(app, String(format: "%02d-%@", i + 2, v.lowercased().replacingOccurrences(of: " ", with: "-")))
        }
        XCTAssertTrue(web.buttons.matching(NSPredicate(format: "label CONTAINS 'Research Results'")).firstMatch.exists)
    }

    @MainActor
    func testBackgroundPausesAndForegroundNotifies() throws {
        let app = XCUIApplication()
        app.launch()
        let web = app.webViews.firstMatch
        let run = web.buttons.matching(NSPredicate(format: "label CONTAINS 'Run'")).firstMatch
        XCTAssertTrue(run.waitForExistence(timeout: 240))  // a cold first launch on a fresh simulator is slow
        run.tap()
        sleep(2)
        XCUIDevice.shared.press(.home)
        // only a real transition to the background pauses (an inactive app — banner, control centre — keeps running,
        // and iOS has not suspended it); the transition can take several seconds on a loaded simulator
        XCTAssertTrue(app.wait(for: .runningBackground, timeout: 30) || app.wait(for: .runningBackgroundSuspended, timeout: 5),
                      "the app did not reach the background")
        sleep(2)
        app.activate()
        let notice = web.staticTexts.matching(NSPredicate(format: "label CONTAINS 'paused while the app was in the background'")).firstMatch
        XCTAssertTrue(notice.waitForExistence(timeout: 10))
        XCTAssertTrue(web.buttons.matching(NSPredicate(format: "label CONTAINS 'Run'")).firstMatch.exists, "paused after resume")
        shot(app, "lifecycle-resumed")
    }
}
