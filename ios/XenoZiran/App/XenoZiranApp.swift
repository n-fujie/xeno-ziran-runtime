import SwiftUI
import UIKit
import os

@main
struct XenoZiranApp: App {
    init() {
        SimulatorRuntime.shared.start()  // the interpreter starts while the interface loads
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @StateObject private var host = WebHost()
    @Environment(\.scenePhase) private var phase
    @State private var runtimeState: SimulatorRuntime.State = .starting

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            SimulatorWebView(host: host)
                .ignoresSafeArea(.container, edges: .bottom)
                .opacity(host.loaded ? 1 : 0)
            if case .failed(let message) = runtimeState {
                RuntimeFailureView(message: message)
            } else if !host.loaded || runtimeState != .ready {
                StartingView()
            }
        }
        .preferredColorScheme(.dark)
        .alert("Simulator", isPresented: Binding(get: { host.pageError != nil }, set: { if !$0 { host.pageError = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(host.pageError ?? "")
        }
        .task {
            await SimulatorRuntime.shared.ready()
            runtimeState = SimulatorRuntime.shared.state
        }
        .onChange(of: phase) { old, new in
            Logger(subsystem: "io.platodesign.xenoziransimulator", category: "app")
                .notice("scene phase \(String(describing: old), privacy: .public) → \(String(describing: new), privacy: .public)")
            switch new {
            case .background: host.enterBackground()
            case .active: host.enterForeground()
            default: break
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didReceiveMemoryWarningNotification)) { _ in
            Task { await host.memoryWarning() }
        }
    }
}

struct StartingView: View {
    var body: some View {
        VStack(spacing: 14) {
            ProgressView().tint(.white)
            Text("XENO ZIRAN SIMULATOR")
                .font(.system(size: 15, weight: .semibold, design: .monospaced))
                .foregroundStyle(.white)
            Text("Starting the on-device simulation runtime…")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Starting the on-device simulation runtime")
        .accessibilityIdentifier("starting")
    }
}

struct RuntimeFailureView: View {
    let message: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("The simulator runtime could not start")
                .font(.headline)
            Text("The simulation engine runs on this device. It could not be started, so no simulation is available "
                 + "in this session. Nothing was sent anywhere. Restarting the app usually resolves this; if it does "
                 + "not, the desktop runtime offers the same simulator.")
                .font(.callout)
                .foregroundStyle(.secondary)
            Text(message)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
        }
        .padding(24)
        .frame(maxWidth: 560)
        .foregroundStyle(.white)
        .accessibilityIdentifier("runtime-failure")
    }
}
