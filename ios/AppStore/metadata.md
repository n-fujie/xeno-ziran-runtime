# XENO ZIRAN SIMULATOR — App Store / TestFlight metadata (final draft)

Status (2026-10-06, 20:20 JST): app record **6819625252** exists (primary language English (U.K.)); build
**1.0 (1)** uploaded, Apple processing state **VALID**, internal TestFlight state **READY_FOR_BETA_TESTING**.
Nothing has been submitted for App Review or Beta App Review. The texts below are ready to paste into the version
page; the privacy policy still needs a public URL before App Store submission.

## App record

| Field | Value |
|---|---|
| Name | XENO ZIRAN SIMULATOR |
| Bundle ID | `io.platodesign.xenoziransimulator` (app ID 6819625252) |
| SKU | `xeno-ziran-simulator-ios` |
| Platform | iOS (iPhone + iPad), iOS 17.0 or later |
| Primary language | English (U.K.) — as created in App Store Connect |
| Version / build | 1.0 (1) uploaded — the next upload must use build 2 or higher |
| Primary / secondary category | Education / Reference |
| Price | Free (owner's decision) |
| Copyright | © 2026 NAOTO FUJIE |
| Support URL | https://ziran-xeno-simulator.vercel.app |
| Marketing URL | https://ziran-xeno-simulator.vercel.app |
| Privacy policy URL | **to be published** — text below; smallest path in "Privacy policy" |

## Subtitle (≤ 30)

Operational-shape simulator

## Promotional text (≤ 170)

Run the XENO ZIRAN SIMULATOR on your device: watch differences propagate across configurations, intervene, and
compare branches — the simulation runs locally, without a server.

## Description

XENO ZIRAN SIMULATOR is an environment for exploring how differences propagate across configurations under
changes in scale, topology, memory, coupling, observation, history, boundary and intervention. It does not fix the
variables, state space, observer or ontology in advance.

The interactive simulator runs locally on your device and does not transmit simulation state, imported files, or usage data. Network access occurs only when you explicitly open external research resources in Safari. No account is needed and no server is involved.

• Network, Shape Space, Address Space, World Map and 3D Globe projections of the same evolving world, with scale
  navigation from regions down to single configurations
• Run, pause, step and rewind to checkpoints
• Timeline of the run's descriptors and detected events
• Philosophical Practice: state concepts, claims and interventions in a small command language, see their
  dependencies and operational consequences, then apply them
• Compare: branch the world, run baseline and intervention side by side, and inspect where they diverge
• Save and Load sessions as files compatible with the desktop runtime; export configurations, connections,
  events and metrics as CSV or JSON through the share sheet

On phone and tablet the simulator handles bundled worlds of up to 3,000 configurations. Larger worlds, long
experiment runs and the published research results belong to the desktop runtime and the research-results site
(ziran-xeno-simulator.vercel.app), which the app links to.

The simulator is an experimental and analytical environment. Its outputs are not real-world forecasts or
predictive claims.

## Keywords (≤ 100)

simulation,complex systems,networks,graph,emergence,philosophy,research,dynamics,intervention,offline

## Version notes (1.0)

First release of the on-device XENO ZIRAN SIMULATOR: the interactive simulator, its eight views, comparison,
Philosophical Practice, and desktop-compatible Save/Load, running locally on iPhone and iPad.

## TestFlight — What to Test (internal, build 1)

First internal build. The simulator runs locally on the device; no server is needed.
1. Launch (also in airplane mode): a session builds and Run / Pause / Step / Rewind work.
2. Open Network, Shape Space, Address Space, World Map, 3D Globe, Timeline, Compare, Philosophical Practice.
3. Practice: `remove concept human`, then `apply`; the comparison reports.
4. Save to Files and Load the file again; also Load a Save file made by the desktop runtime.
5. Send the app to the background while running and return: the simulation is paused and says so.
6. Known mobile limits: worlds up to 3,000 configurations / 48,000 connections, 2 sessions, comparisons up to 300
   steps, exports up to 25 MB. Larger workloads are refused with a message and remain available in the desktop
   runtime.

## App Review notes

Privacy in one sentence: The interactive simulator runs locally on the device and does not transmit simulation state, imported files, or usage data. Network access occurs only when the user explicitly opens external research resources in Safari.

XENO ZIRAN SIMULATOR is a self-contained scientific simulator. How it works:

- The simulation engine is written in Python. The Python runtime (CPython 3.14), numpy and the engine's Python
  code are bundled inside the signed app; the bytecode is compiled at build time. The app's functionality is
  fixed in the reviewed build: it never downloads Python code, scripts or any other executable content.
- The app does not execute code provided by users. Users act on the simulation through buttons and a small fixed
  command language (for example "remove concept human"), which is parsed by a fixed grammar and translated into
  predefined simulation operations — it is not evaluated as code.
- There is no shell and no subprocess execution available to users. The interpreter is shipped without its
  networking modules (sockets, SSL/HTTP); the simulator does not need them.
- The interface is a bundled web page shown in a WKWebView. It is served from the app bundle only; it loads no
  remote pages, scripts, styles or fonts (a Content-Security-Policy forbids network connections), and navigation
  outside the bundled page is blocked.
- The page communicates with the native code through one message handler that accepts only a fixed allowlist of
  simulator operations (create session, step, rewind, compare, save, export, …); anything else is rejected.
- The simulation runs locally on the device; no account, server or network connection is required. The only
  outbound action is an explicit "Research Results ↗" link, which opens the project's public research-results
  website in Safari.
- Saved sessions and exports are written only where the user chooses through the system share sheet.

To try it: launch the app — a demo world (3,000 configurations) builds in a few seconds — then press Run, switch
views with the tabs, and open Compare or Philosophical Practice.

## App Privacy (App Store Connect questionnaire) — recommended answers

**Do you or your third-party partners collect data from this app? → No, we do not collect data from this app.**

Statement: The interactive simulator runs locally on the device and does not transmit simulation state, imported files, or usage data. Network access occurs only when the user explicitly opens external research resources in Safari.

Basis (verified in the current build):

| Behaviour | Fact |
|---|---|
| Simulation state | Held in memory on the device while the app runs; never transmitted. Sessions are not persisted by the app. |
| Imported files (Load) | Read on the device from a file the user picks; never transmitted. |
| Exported files (Save / Export) | Written only where the user sends them through the system share sheet, by the user's action. |
| External research link | Opens the public research-results website in Safari when the user taps it; the app itself sends nothing. |
| Automatic network requests by the app | None (audited: 0 internet sockets in the app and its web-view processes during a running session). |
| Analytics / tracking / advertising / third-party SDKs | None. |
| Server-side simulation state | None exists. |

Tracking: **No.** Privacy manifest (`PrivacyInfo.xcprivacy`): no tracking, no collected data types, one
required-reason API declaration (file timestamps, reason C617.1 — the interpreter checks timestamps of files in
its own bundle).

## Export compliance — recommended answer

`ITSAppUsesNonExemptEncryption = NO` (set in Info.plist), i.e. "None of the algorithms mentioned above" / no
encryption. Basis: the app performs no encryption and makes no network connections of its own. The embedded
interpreter is shipped without its OpenSSL-based modules (`_ssl`, `_hashlib`) and without socket support; the
remaining hash functions (SHA-256 for identifying cached hierarchies) are hashing, not encryption. Any HTTPS
loading of the research-results website happens in Safari, outside the app.

## Age rating — recommended answers

All content descriptors: **None** (no violence, sexual content, profanity, horror, drugs/alcohol/tobacco,
gambling or simulated gambling, contests, medical/treatment information). Unrestricted web access: **No** (the app
shows only its bundled interface; the single research link opens Safari). User-generated content shared with
others / messaging / social features: **No**. In-app purchases: **No**. Advertising: **No**. Parental controls /
age assurance: not applicable. Expected rating: **4+**.

## Privacy policy (text to publish)

> **XENO ZIRAN SIMULATOR — Privacy Policy**
>
> XENO ZIRAN SIMULATOR runs its interactive simulation locally on your device.
>
> - The app does not transmit simulation state or files you import. It contains no analytics, tracking or
>   advertising, and it does not create accounts.
> - Saving and exporting are under your control: files are written only where you choose through the system
>   share sheet.
> - The app makes no automatic network requests. If you tap a link to the project's research-results website, it
>   opens in your browser, which then connects to that website.
> - Apple processes standard data related to App Store and TestFlight distribution (for example downloads, crash
>   reports you choose to share, TestFlight feedback) under Apple's own privacy policy, outside the app's control.
>
> Contact: llcterraio@gmail.com

Smallest publication path: add this text as a static page to the existing research-results site (e.g.
`/privacy`, a `site/privacy/index.html` in the static mirror, deployed with the existing Vercel workflow) — this
needs the owner's go-ahead because it changes the production site; it was not deployed.

## Screenshots

`ios/AppStore/screenshots/iphone-6.9/` (1320 × 2868, iPhone 17 Pro Max simulator) and
`ios/AppStore/screenshots/ipad-13/` (2064 × 2752, iPad Pro 13-inch M5 simulator): 8 each — running, Network,
Shape Space, World Map, 3D Globe, Timeline, Compare, Philosophical Practice — captured by the UI tests from the
current interface (Save / Load / Export visible, no debug overlays, no missing glyphs). Simulator captures, not
photographs of a device.

## Known mobile limits (state them; never hide them)

| limit | iOS app | desktop runtime |
|---|---|---|
| configurations | 3,000 | 500,000 |
| connections | 48,000 | 32,000,000 |
| concurrent sessions | 2 | 4 |
| comparison horizon | 300 steps | 5,000 |
| export size | 25 MB | 2 GB |

Larger workloads are refused with a message naming the limit and the desktop runtime; nothing is silently reduced.
