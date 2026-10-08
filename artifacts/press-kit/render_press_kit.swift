// Renders the launch / investor press images from the current app screenshots and the Z logo.
//   swift render_press_kit.swift <logo.png> <out-dir>
import AppKit
import Foundation

let args = CommandLine.arguments
let logoPath = args[1]
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
let shots = "/Users/user/Desktop/BIM/xeno-ziran-runtime/ios/AppStore/screenshots"
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

// ---------------------------------------------------------------- palette & helpers
let bg = NSColor(srgbRed: 0.02, green: 0.02, blue: 0.03, alpha: 1)
let fg = NSColor(srgbRed: 0.93, green: 0.93, blue: 0.95, alpha: 1)
let dim = NSColor(srgbRed: 0.62, green: 0.62, blue: 0.67, alpha: 1)
let faint = NSColor(srgbRed: 0.36, green: 0.36, blue: 0.40, alpha: 1)
let bezel = NSColor(srgbRed: 0.13, green: 0.13, blue: 0.15, alpha: 1)

func image(_ path: String) -> NSImage { NSImage(contentsOfFile: path)! }
func phone(_ name: String) -> NSImage { image("\(shots)/iphone-6.9/\(name).png") }
func pad(_ name: String) -> NSImage { image("\(shots)/ipad-13/\(name).png") }

/// The Z mark: the symbol part of the logo (without the word mark), black → white for dark backgrounds.
let zMark: NSImage = {
    // crop the symbol, then build a white mark whose alpha is the darkness of the logo stroke; the off-white logo
    // background (≈ 0.96) is thresholded to fully transparent so no box shows on dark backgrounds
    let src = image(logoPath)
    let cg = src.cgImage(forProposedRect: nil, context: nil, hints: nil)!
    let w = cg.width, h = cg.height
    let crop = CGRect(x: Int(Double(w) * 0.20), y: Int(Double(h) * 0.26), width: Int(Double(w) * 0.60), height: Int(Double(h) * 0.35))
    let c = cg.cropping(to: crop)!
    let cw = c.width, chh = c.height
    var px = [UInt8](repeating: 0, count: cw * chh * 4)
    let cs = CGColorSpaceCreateDeviceRGB()
    let ctx = CGContext(data: &px, width: cw, height: chh, bitsPerComponent: 8, bytesPerRow: cw * 4, space: cs,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.draw(c, in: CGRect(x: 0, y: 0, width: cw, height: chh))
    for i in stride(from: 0, to: px.count, by: 4) {
        let r: Double = Double(px[i]), g: Double = Double(px[i + 1]), b: Double = Double(px[i + 2])
        let lum: Double = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        let raw: Double = (0.88 - lum) / 0.70  // ≥ 0.88 (background) → 0; ≤ 0.18 (stroke) → 1
        let a: Double = max(0.0, min(1.0, raw))
        let v = UInt8(242.0 * a)  // premultiplied near-white
        px[i] = v
        px[i + 1] = v
        px[i + 2] = UInt8(247.0 * a)
        px[i + 3] = UInt8(255.0 * a)
    }
    let out = ctx.makeImage()!
    return NSImage(cgImage: out, size: NSSize(width: cw, height: chh))
}()

func font(_ size: CGFloat, _ weight: NSFont.Weight = .regular, jp: Bool = false, mono: Bool = false) -> NSFont {
    if jp { return NSFont(name: weight == .regular ? "HiraginoSans-W3" : "HiraginoSans-W6", size: size) ?? .systemFont(ofSize: size) }
    if mono { return .monospacedSystemFont(ofSize: size, weight: weight) }
    return .systemFont(ofSize: size, weight: weight)
}

func text(_ s: String, _ f: NSFont, _ color: NSColor, at p: NSPoint, width: CGFloat, kern: CGFloat = 0, lineSpacing: CGFloat = 4,
          align: NSTextAlignment = .left) -> CGFloat {
    let ps = NSMutableParagraphStyle()
    ps.lineSpacing = lineSpacing
    ps.alignment = align
    let a = NSAttributedString(string: s, attributes: [.font: f, .foregroundColor: color, .kern: kern, .paragraphStyle: ps])
    let r = a.boundingRect(with: NSSize(width: width, height: 10_000), options: [.usesLineFragmentOrigin, .usesFontLeading])
    a.draw(with: NSRect(x: p.x, y: p.y - r.height, width: width, height: r.height), options: [.usesLineFragmentOrigin, .usesFontLeading])
    return r.height  // drawn downward from p (top-left in flipped terms below)
}

/// A device: screenshot with rounded corners inside a dark bezel. `rect` = outer frame.
func device(_ img: NSImage, in rect: NSRect, radius: CGFloat, border: CGFloat) {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.85)
    shadow.shadowBlurRadius = rect.width * 0.08
    shadow.shadowOffset = NSSize(width: 0, height: -rect.width * 0.02)
    NSGraphicsContext.saveGraphicsState()
    shadow.set()
    bezel.setFill()
    NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
    NSGraphicsContext.restoreGraphicsState()
    NSColor(white: 0.32, alpha: 1).setStroke()
    let edge = NSBezierPath(roundedRect: rect.insetBy(dx: 0.5, dy: 0.5), xRadius: radius, yRadius: radius)
    edge.lineWidth = 1
    edge.stroke()
    let inner = rect.insetBy(dx: border, dy: border)
    NSGraphicsContext.saveGraphicsState()
    NSBezierPath(roundedRect: inner, xRadius: radius - border, yRadius: radius - border).addClip()
    img.draw(in: inner)
    NSGraphicsContext.restoreGraphicsState()
}

func phoneRect(x: CGFloat, y: CGFloat, height h: CGFloat) -> NSRect {
    let w = h * 1320 / 2868 + h * 0.03
    return NSRect(x: x, y: y, width: w, height: h)
}

func glow(_ size: NSSize, center: NSPoint, radius: CGFloat, alpha: CGFloat) {
    let g = NSGradient(colors: [NSColor(srgbRed: 0.55, green: 0.6, blue: 0.75, alpha: alpha), .clear])!
    g.draw(fromCenter: center, radius: 0, toCenter: center, radius: radius, options: [])
}

func render(_ name: String, _ size: NSSize, _ draw: (NSSize) -> Void) {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width), pixelsHigh: Int(size.height), bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0,
                               bitsPerPixel: 0)!
    rep.size = size
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSGraphicsContext.current?.imageInterpolation = .high
    bg.setFill()
    NSRect(origin: .zero, size: size).fill()
    draw(size)
    NSGraphicsContext.restoreGraphicsState()
    // flatten to opaque JPEG-quality PNG (no alpha) — friendlier for every platform
    let data = rep.representation(using: .png, properties: [:])!
    try! data.write(to: outDir.appendingPathComponent(name))
    print("wrote", name)
}

func mark(at p: NSPoint, height h: CGFloat) {
    let w = h * zMark.size.width / zMark.size.height
    zMark.draw(in: NSRect(x: p.x, y: p.y, width: w, height: h))
}

let footnoteEN = "Simulation outputs are experimental and analytical — not real-world forecasts."
let footnoteJP = "シミュレーションの出力は実験的・分析的な結果であり、現実世界の予測ではありません。"

// ---------------------------------------------------------------- 1. hero 16:9 (EN / JP)
func hero(_ file: String, jp: Bool) {
    render(file, NSSize(width: 1600, height: 900)) { s in
        glow(s, center: NSPoint(x: 1180, y: 470), radius: 620, alpha: 0.16)
        mark(at: NSPoint(x: 96, y: 690), height: 84)
        _ = text("XENO ZIRAN SIMULATOR", font(46, .semibold), fg, at: NSPoint(x: 96, y: 650), width: 760, kern: 4)
        let tag = jp ? "差異が配置を横断してどう伝わるかを探るシミュレーター。\niPhone と iPad の上で、すべて端末内で動作。"
                     : "An operational-shape simulator.\nRunning entirely on iPhone and iPad."
        _ = text(tag, font(jp ? 25 : 30, .regular, jp: jp), dim, at: NSPoint(x: 96, y: 575), width: 700, lineSpacing: jp ? 10 : 6)
        let bullets = jp
            ? ["端末内でシミュレーションを実行（サーバー不要・オフライン）", "8つのインタラクティブビュー：ネットワーク・形態空間・世界地図・3D地球儀ほか",
               "介入・比較・巻き戻し、デスクトップ版と互換の保存/読み込み"]
            : ["The full simulation engine runs on-device — no server, works offline", "8 interactive views: network, shape space, world map, 3D globe and more",
               "Intervene, compare branches, rewind — desktop-compatible Save / Load"]
        var y: CGFloat = 430
        for b in bullets {
            NSColor(white: 0.85, alpha: 1).setFill()
            NSBezierPath(ovalIn: NSRect(x: 100, y: y - 17, width: 7, height: 7)).fill()
            y -= text(b, font(jp ? 19 : 20, .regular, jp: jp), fg, at: NSPoint(x: 122, y: y), width: 740, lineSpacing: 4) + 20
        }
        _ = text(jp ? footnoteJP : footnoteEN, font(jp ? 13 : 14, .regular, jp: jp), faint, at: NSPoint(x: 96, y: 92), width: 760)
        device(phone("03-shape-space"), in: phoneRect(x: 900, y: 150, height: 600), radius: 46, border: 9)
        device(phone("02-network"), in: phoneRect(x: 1215, y: 105, height: 690), radius: 52, border: 10)
    }
}
hero("01_hero_16x9_en.png", jp: false)
hero("02_hero_16x9_ja.png", jp: true)

// ---------------------------------------------------------------- 2. four views, square
render("03_views_square_1080.png", NSSize(width: 1080, height: 1080)) { s in
    glow(s, center: NSPoint(x: 540, y: 470), radius: 560, alpha: 0.12)
    mark(at: NSPoint(x: 64, y: 980), height: 46)
    _ = text("XENO ZIRAN SIMULATOR", font(30, .semibold), fg, at: NSPoint(x: 152, y: 1016), width: 800, kern: 3)
    _ = text("One evolving world — many ways to look at it", font(20), dim, at: NSPoint(x: 64, y: 950), width: 960)
    let items = [("02-network", "Network"), ("03-shape-space", "Shape Space"), ("05-world-map", "World Map"), ("07-timeline", "Timeline")]
    let h: CGFloat = 640
    let w = phoneRect(x: 0, y: 0, height: h).width
    let gap = (s.width - 4 * w) / 5
    for (i, it) in items.enumerated() {
        let x = gap + CGFloat(i) * (w + gap)
        device(phone(it.0), in: NSRect(x: x, y: 150, width: w, height: h), radius: 34, border: 7)
        _ = text(it.1, font(19, .medium), fg, at: NSPoint(x: x - 20, y: 128), width: w + 40, align: .center)
    }
    _ = text(footnoteEN, font(13), faint, at: NSPoint(x: 64, y: 52), width: 960)
}

// ---------------------------------------------------------------- 3. iPad 16:9
render("04_ipad_16x9.png", NSSize(width: 1600, height: 900)) { s in
    glow(s, center: NSPoint(x: 1050, y: 450), radius: 700, alpha: 0.13)
    mark(at: NSPoint(x: 90, y: 700), height: 70)
    _ = text("Built for iPad, too", font(44, .semibold), fg, at: NSPoint(x: 90, y: 650), width: 460)
    _ = text("Shape Space with the inspector side by side: operational descriptors, recurrent shapes and the configuration under the cursor.",
             font(21), dim, at: NSPoint(x: 90, y: 570), width: 430, lineSpacing: 6)
    _ = text("XENO ZIRAN SIMULATOR", font(18, .semibold), fg, at: NSPoint(x: 90, y: 200), width: 460, kern: 3)
    _ = text(footnoteEN, font(13), faint, at: NSPoint(x: 90, y: 150), width: 430)
    let h: CGFloat = 760
    let w = h * 2064 / 2752 + 24
    device(pad("03-shape-space"), in: NSRect(x: 600, y: 70, width: w, height: h), radius: 34, border: 12)
}

// ---------------------------------------------------------------- 4. facts (EN / JP), square — measured or factual only
func facts(_ file: String, jp: Bool) {
    render(file, NSSize(width: 1080, height: 1080)) { s in
        glow(s, center: NSPoint(x: 900, y: 900), radius: 520, alpha: 0.12)
        mark(at: NSPoint(x: 72, y: 940), height: 64)
        _ = text("XENO ZIRAN SIMULATOR", font(30, .semibold), fg, at: NSPoint(x: 72, y: 900), width: 900, kern: 3)
        _ = text(jp ? "数字で見る" : "By the numbers", font(22, .regular, jp: jp), dim, at: NSPoint(x: 72, y: 850), width: 900)
        let rows: [(String, String)] = jp ? [
            ("100%", "シミュレーションは端末内で実行。サーバー・アカウント不要、オフラインで動作"),
            ("8", "インタラクティブビュー（ネットワーク、形態空間、アドレス空間、世界地図、3D地球儀、タイムライン、比較、哲学的実践）"),
            ("2,048,000", "単一ランで検証済みの最大配置数（約980万接続）— Apple M1・8GB ノートで計測"),
            ("0", "同じシードでの再実行時の差分 — 結果は決定的に再現"),
        ] : [
            ("100%", "of the simulation runs on-device — no server, no account, works offline"),
            ("8", "interactive views: network, shape space, address space, world map, 3D globe, timeline, compare, practice"),
            ("2,048,000", "configurations in a single verified run (9.8 M connections) — measured on an Apple M1 laptop with 8 GB"),
            ("0", "differences between reruns with the same seed — results are deterministic"),
        ]
        var y: CGFloat = 770
        for (big, desc) in rows {
            _ = text(big, font(56, .bold), fg, at: NSPoint(x: 72, y: y), width: 360)
            let hgt = text(desc, font(jp ? 20 : 22, .regular, jp: jp), dim, at: NSPoint(x: 440, y: y - 10), width: 570, lineSpacing: 5)
            y -= max(120, hgt + 60)
            NSColor(white: 0.18, alpha: 1).setFill()
            NSRect(x: 72, y: y + 34, width: 936, height: 1).fill()
        }
        _ = text(jp ? footnoteJP : footnoteEN, font(14, .regular, jp: jp), faint, at: NSPoint(x: 72, y: 70), width: 936)
    }
}
facts("05_facts_square_en.png", jp: false)
facts("06_facts_square_ja.png", jp: true)

// ---------------------------------------------------------------- 5. portrait singles 1080x1350 (Instagram)
let singles = [("02-network", "Network", "Watch differences ignite and propagate across a field of configurations."),
               ("06-3d-globe", "3D Globe", "The same world projected onto a globe — one projection among several."),
               ("08-compare", "Compare", "Branch the world and compare baseline and intervention, side by side."),
               ("07-timeline", "Timeline", "Every run's descriptors and detected events over time — rewind to any checkpoint.")]
for (i, sgl) in singles.enumerated() {
    render(String(format: "%02d_portrait_%@.png", 7 + i, sgl.1.lowercased().replacingOccurrences(of: " ", with: "-")),
           NSSize(width: 1080, height: 1350)) { s in
        glow(s, center: NSPoint(x: 540, y: 560), radius: 600, alpha: 0.14)
        mark(at: NSPoint(x: 72, y: 1236), height: 46)
        _ = text("XENO ZIRAN SIMULATOR", font(24, .semibold), dim, at: NSPoint(x: 152, y: 1270), width: 800, kern: 3)
        _ = text(sgl.1, font(52, .bold), fg, at: NSPoint(x: 72, y: 1190), width: 936)
        _ = text(sgl.2, font(24), dim, at: NSPoint(x: 72, y: 1110), width: 936, lineSpacing: 6)
        let h: CGFloat = 900
        let w = phoneRect(x: 0, y: 0, height: h).width
        device(phone(sgl.0), in: NSRect(x: (s.width - w) / 2, y: 90, width: w, height: h), radius: 54, border: 11)
        _ = text(footnoteEN, font(13), faint, at: NSPoint(x: 72, y: 50), width: 936, align: .center)
    }
}
