// Floating progress window for `mlx-transcribe --progress-window`.
//
// Reads lines from stdin: "<fraction 0..1 or -1 for indeterminate>\t<title>\t<detail>".
// Closes when stdin hits EOF; Cancel exits with status 1 so the parent can stop.
// Built by install.sh into ~/Library/Application Support/mlx-transcripter/progress.
import AppKit

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // no Dock icon

let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 420, height: 112),
                    styleMask: [.titled, .nonactivatingPanel, .utilityWindow, .hudWindow],
                    backing: .buffered, defer: false)
panel.title = "Transcribing"
panel.level = .floating
panel.isFloatingPanel = true
panel.hidesOnDeactivate = false
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

let title = NSTextField(labelWithString: "Preparing…")
title.font = .boldSystemFont(ofSize: 13)
title.lineBreakMode = .byTruncatingMiddle
let detail = NSTextField(labelWithString: "")
detail.font = .monospacedDigitSystemFont(ofSize: 11, weight: .regular)
detail.textColor = .secondaryLabelColor
let bar = NSProgressIndicator()
bar.style = .bar
bar.minValue = 0
bar.maxValue = 1
bar.isIndeterminate = true
bar.startAnimation(nil)

final class Actions: NSObject {
    @objc func cancel() { exit(1) }
}
let actions = Actions()
let cancel = NSButton(title: "Cancel", target: actions, action: #selector(Actions.cancel))
cancel.controlSize = .small

let row = NSStackView(views: [detail, NSView(), cancel])
row.orientation = .horizontal
let stack = NSStackView(views: [title, bar, row])
stack.orientation = .vertical
stack.alignment = .leading
stack.spacing = 8
stack.edgeInsets = NSEdgeInsets(top: 14, left: 16, bottom: 12, right: 16)
for v in [bar, row] { v.translatesAutoresizingMaskIntoConstraints = false }
panel.contentView = stack
NSLayoutConstraint.activate([
    bar.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -32),
    row.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -32),
])

// Top-right corner, under the menu bar, like a notification.
if let screen = NSScreen.main?.visibleFrame {
    panel.setFrameTopLeftPoint(NSPoint(x: screen.maxX - panel.frame.width - 16, y: screen.maxY - 16))
}
panel.orderFrontRegardless()

Thread.detachNewThread {
    while let line = readLine() {
        let parts = line.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
        guard parts.count >= 3, let frac = Double(parts[0]) else { continue }
        DispatchQueue.main.async {
            title.stringValue = parts[1]
            detail.stringValue = parts[2]
            if frac < 0 {
                bar.isIndeterminate = true
                bar.startAnimation(nil)
            } else {
                bar.stopAnimation(nil)
                bar.isIndeterminate = false
                bar.doubleValue = frac
            }
        }
    }
    DispatchQueue.main.async { exit(0) }
}

app.run()
