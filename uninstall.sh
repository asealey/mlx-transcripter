#!/bin/zsh
# Remove everything install.sh added. The cached Whisper model stays in
# ~/.cache/huggingface (delete models--mlx-community--whisper-large-v3-turbo there to reclaim it).
set -uo pipefail

uv tool uninstall mlx-transcripter 2>/dev/null
rm -rf "$HOME/Library/Application Support/mlx-transcripter"
rm -rf "$HOME/Library/Services/Transcribe to Text.workflow" \
       "$HOME/Library/Services/Transcribe to Subtitles (SRT).workflow"
# Drop the two enable entries via defaults (not by editing the plist, which cfprefsd caches).
defaults export pbs - | /usr/bin/python3 -c '
import plistlib, sys
d = plistlib.loads(sys.stdin.buffer.read())
for n in ("Transcribe to Text", "Transcribe to Subtitles (SRT)"):
    d.get("NSServicesStatus", {}).pop(f"(null) - {n} - runWorkflowAsService", None)
sys.stdout.buffer.write(plistlib.dumps(d))' | defaults import pbs -
/System/Library/CoreServices/pbs -update
echo "Uninstalled. Logs remain at ~/Library/Logs/mlx-transcripter.log."
