"""Build the Finder Quick Actions into ~/Library/Services (run by install.sh).

Each one is a one-step Automator "Run Shell Script" workflow that hands the
selected files to the installed `mlx-transcribe` command, which shows a floating
progress window and posts a notification when done. It runs in the foreground
so the menu-bar gear stays up (and can stop it) until the transcript is written. Output lands next to each file; logs go to
~/Library/Logs/mlx-transcripter.log.
"""

import plistlib
import sys
import uuid
from pathlib import Path

SERVICES = Path.home() / "Library/Services"
FILE_TYPES = ["public.audio", "public.movie", "public.audiovisual-content"]
ACTIONS = {
    "Transcribe to Text": "txt",
    "Transcribe to Subtitles (SRT)": "srt",
}

SCRIPT = """export PATH="{bin}:/opt/homebrew/bin:/usr/local/bin:$PATH"
export HF_HUB_OFFLINE=1  # model is cached by install.sh; skip the per-run online check
log="$HOME/Library/Logs/mlx-transcripter.log"
if ! command -v mlx-transcribe >/dev/null; then
  osascript -e 'display notification "Run {repo}/install.sh" with title "mlx-transcribe not installed"'
  exit 1
fi
# mlx-transcribe reports failures/cancel itself; a non-zero exit here would just add an Automator alert.
mlx-transcribe --format {fmt} --force --notify --progress-window "$@" >>"$log" 2>&1 || true
"""


def info_plist(name: str) -> dict:
    return {"NSServices": [{
        "NSMenuItem": {"default": name},
        "NSMessage": "runWorkflowAsService",
        "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
        "NSSendFileTypes": FILE_TYPES,
        "NSIconName": "NSActionTemplate",
    }]}


def document(script: str) -> dict:
    args = [("inputMethod", 0), ("CheckedForUserDefaultShell", False), ("source", ""),
            ("COMMAND_STRING", ""), ("shell", "/bin/sh")]
    action = {
        "AMAccepts": {"Container": "List", "Optional": True, "Types": ["com.apple.cocoa.string"]},
        "AMActionVersion": "2.0.3",
        "AMApplication": ["Automator"],
        "AMParameterProperties": {k: {} for k, _ in args},
        "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
        "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
        "ActionName": "Run Shell Script",
        "ActionParameters": {
            "COMMAND_STRING": script,
            "CheckedForUserDefaultShell": True,
            "inputMethod": 1,  # selected files arrive as "$@"
            "shell": "/bin/zsh",
            "source": "",
        },
        "BundleIdentifier": "com.apple.RunShellScript",
        "CFBundleVersion": "2.0.3",
        "CanShowSelectedItemsWhenRun": False,
        "CanShowWhenRun": True,
        "Category": ["AMCategoryUtilities"],
        "Class Name": "RunShellScriptAction",
        "InputUUID": str(uuid.uuid4()).upper(),
        "OutputUUID": str(uuid.uuid4()).upper(),
        "UUID": str(uuid.uuid4()).upper(),
        "UnlocalizedApplications": ["Automator"],
        "arguments": {str(i): {"default value": d, "name": n, "required": "0", "type": "0", "uuid": str(i)}
                      for i, (n, d) in enumerate(args)},
        "isViewVisible": 1,
        "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib",
    }
    finder = "/System/Library/CoreServices/Finder.app"
    meta = {
        "applicationBundleID": "com.apple.finder",
        "applicationBundleIDsByPath": {finder: "com.apple.finder"},
        "applicationPath": finder,
        "applicationPaths": [finder],
        "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
        "outputTypeIdentifier": "com.apple.Automator.nothing",
        "presentationMode": 15,
        "processesInput": False,
        "serviceApplicationBundleID": "com.apple.finder",
        "serviceApplicationPath": finder,
        "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
        "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
        "serviceProcessesInput": False,
        "systemImageName": "NSActionTemplate",
        "useAutomaticInputType": False,
        "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
    }
    return {"AMApplicationBuild": "534", "AMApplicationVersion": "2.10", "AMDocumentVersion": "2",
            "actions": [{"action": action, "isViewVisible": 1}], "connectors": {},
            "workflowMetaData": meta}


def main() -> None:
    bin_dir = sys.argv[1]  # where `uv tool` put the mlx-transcribe executable
    repo = Path(__file__).resolve().parent
    for name, fmt in ACTIONS.items():
        contents = SERVICES / f"{name}.workflow" / "Contents"
        contents.mkdir(parents=True, exist_ok=True)
        (contents / "Info.plist").write_bytes(plistlib.dumps(info_plist(name)))
        (contents / "document.wflow").write_bytes(
            plistlib.dumps(document(SCRIPT.format(bin=bin_dir, fmt=fmt, repo=repo))))
        print(f"installed Quick Action: {name}")


if __name__ == "__main__":
    main()
