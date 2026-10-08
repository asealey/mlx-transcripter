#!/bin/zsh
# Install the `mlx-transcribe` command (editable, so code changes apply immediately),
# the progress window, and the Finder Quick Actions. Safe to re-run; undo with uninstall.sh.
set -euo pipefail
cd "${0:A:h}"

if [[ $(uname -m) != arm64 ]]; then echo "mlx-transcripter needs an Apple Silicon Mac" >&2; exit 1; fi
for tool in uv ffmpeg xcrun; do
  command -v $tool >/dev/null || { echo "missing $tool (brew install uv ffmpeg; xcode-select --install)" >&2; exit 1; }
done

uv tool install --force --editable .
bin_dir=$(uv tool dir --bin)
support="$HOME/Library/Application Support/mlx-transcripter"
mkdir -p "$support"
xcrun swiftc -O -o "$support/progress" src/mlx_transcripter/progress.swift
uv run --no-project python make_quick_actions.py "$bin_dir"

# Hand-built workflows aren't enabled by default (Automator does this on save); without it
# they never show under Finder's Quick Actions submenu.
for name in "Transcribe to Text" "Transcribe to Subtitles (SRT)"; do
  defaults write pbs NSServicesStatus -dict-add "\"(null) - $name - runWorkflowAsService\"" \
    '{enabled_context_menu = 1; enabled_services_menu = 1; presentation_modes = {ContextMenu = 1; FinderPreview = 1; ServicesMenu = 1; TouchBar = 1;};}'
done
/System/Library/CoreServices/pbs -update  # refresh the Services menu

# Download the model now (~1.6 GB, once) so the first right-click doesn't stall.
echo "Fetching the Whisper model (first time only)…"
uv run --no-project --with huggingface_hub python -c \
  'from huggingface_hub import snapshot_download as d; d("mlx-community/whisper-large-v3-turbo")' >/dev/null
echo "Done. Right-click an audio/video file in Finder → Quick Actions → Transcribe to Text / Subtitles (SRT)."
