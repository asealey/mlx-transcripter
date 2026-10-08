# mlx-transcripter

Right-click an audio or video file in Finder and get a transcript next to it, transcribed
locally on your Mac's GPU with [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
(`whisper-large-v3-turbo`). Nothing leaves the machine. A 30-minute podcast takes about two
minutes on an M-series Mac.

- **Finder Quick Actions:** *Transcribe to Text* (`.txt`) and *Transcribe to Subtitles (SRT)* (`.srt`)
- **Progress window:** position in the audio, percent done, time left, and Cancel
- **CLI:** `mlx-transcribe` for scripts and batches (txt / srt / timestamped JSON)

## Requirements

- Apple Silicon Mac (MLX doesn't run on Intel)
- [uv](https://docs.astral.sh/uv/) and [ffmpeg](https://ffmpeg.org): `brew install uv ffmpeg`
- Xcode command line tools, for building the progress window: `xcode-select --install`
- About 1.6 GB of disk for the Whisper model, downloaded once during install

## Install

```bash
git clone https://github.com/asealey/mlx-transcripter.git
cd mlx-transcripter
./install.sh
```

Then right-click any audio or video file (or several) → **Quick Actions** →
**Transcribe to Text** or **Transcribe to Subtitles (SRT)**. The transcript appears next to the
original with the same name; an existing one is overwritten. While it runs, a floating window
shows progress and the menu-bar gear spins; when it finishes you hear a chime and get a
notification.

If the actions don't show up, tick them under **Quick Actions → Customize…** (or System Settings →
Keyboard → Keyboard Shortcuts → Services → Files and Folders). Notifications come from Script
Editor, so allow it under System Settings → Notifications if you want them. The chime plays either way.

### What install.sh changes

| Where | What |
|---|---|
| `~/.local/bin/mlx-transcribe`, `transcribe` | the CLI (`uv tool install --editable`, so edits in the clone apply immediately) |
| `~/Library/Application Support/mlx-transcripter/` | the compiled progress window |
| `~/Library/Services/Transcribe to *.workflow` | the two Quick Actions |
| `pbs` preferences (`NSServicesStatus`) | marks both Quick Actions enabled so Finder lists them |
| `~/.cache/huggingface/` | the Whisper model |

Logs go to `~/Library/Logs/mlx-transcripter.log`. `./uninstall.sh` removes everything above
except the model cache and the log.

## CLI

```bash
mlx-transcribe talk.m4a                                   # -> talk.txt next to it
mlx-transcribe --format srt,txt clip.mov                  # -> clip.srt + clip.txt
mlx-transcribe --format json,txt --out transcripts *.mp3  # batch into a folder
```

| Flag | |
|---|---|
| `--format` | any of `txt`, `srt`, `json` (timestamped segments), comma-separated; default `txt` |
| `--out DIR` | write here instead of next to each file |
| `--force` | overwrite existing outputs (otherwise files with outputs are skipped) |
| `--language` | language code, default `en`; `auto` to detect |
| `--model` | any mlx-community Whisper repo, e.g. `mlx-community/whisper-base-mlx` for speed |
| `--progress-window`, `--notify` | the floating progress bar and the done notification + chime |
| `--limit N` | stop after N files |

Running several copies over the same files is safe: each claims a file with a lock first, so you
can split a big batch across parallel workers.

## License

[MIT](LICENSE)
