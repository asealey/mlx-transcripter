"""Transcribe audio/video files locally with mlx-whisper.

Writes transcripts next to each source file (or into --out), in any mix of
plain text, SRT subtitles and timestamped JSON segments. The model loads once
per run.

    mlx-transcribe talk.m4a                          # -> talk.txt
    mlx-transcribe --format srt,txt clip.mov         # -> clip.srt + clip.txt
    mlx-transcribe --format json,txt --out trans input/*.mp3

Existing outputs are skipped unless --force. Safe to run several copies over
the same files at once: each claims a file with a lock before working on it.
"""

import _thread
import argparse
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
FORMATS = ("txt", "srt", "json")
PROGRESS_APP = Path.home() / "Library/Application Support/mlx-transcripter/progress"  # built by install.sh
FRAMES_PER_SEC = 100  # whisper mel frames (16 kHz audio, hop length 160)


def claim(lock: Path) -> bool:
    """Atomically take a per-file lock; reclaim it if its owner process died."""
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            os.kill(int(lock.read_text() or 0), 0)
            return False  # owner still running
        except (ProcessLookupError, ValueError):
            lock.unlink(missing_ok=True)
            return claim(lock)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def notify(title: str, message: str, sound: str | None = None) -> None:
    """macOS notification; text goes in as argv so quotes in filenames are harmless.

    The sound plays via afplay, so it's heard even if notifications are blocked.
    """
    script = "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"
    subprocess.run(["osascript", "-e", script, title, message], check=False)
    if sound:
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound}.aiff"], check=False)


class ProgressWindow:
    """Feeds the floating progress window (progress.swift). Cancel there interrupts us."""

    def __init__(self) -> None:
        self.proc = None
        self.closing = False
        if PROGRESS_APP.exists():
            self.proc = subprocess.Popen([str(PROGRESS_APP)], stdin=subprocess.PIPE, text=True)
            threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self) -> None:
        if self.proc.wait() != 0 and not self.closing:
            _thread.interrupt_main()  # Cancel pressed -> KeyboardInterrupt in the main thread

    def update(self, fraction: float, title: str, detail: str) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(f"{fraction}\t{title}\t{detail}\n")
                self.proc.stdin.flush()
            except BrokenPipeError:
                pass

    def close(self) -> None:
        if self.proc:
            self.closing = True
            self.proc.stdin.close()
            self.proc.wait()


def hook_progress(callback) -> None:
    """Route mlx-whisper's tqdm bar through callback(done_frames, total_frames)."""
    import tqdm

    mt = importlib.import_module("mlx_whisper.transcribe")

    class Bar(tqdm.tqdm):
        def __init__(self, *a, **kw):
            kw["disable"] = False
            if not sys.stderr.isatty():  # keep \r-spam out of the log file
                kw["file"] = open(os.devnull, "w")
            super().__init__(*a, **kw)

        def update(self, n=1):
            super().update(n)
            callback(self.n, self.total)

    mt.tqdm = types.SimpleNamespace(tqdm=Bar)


def clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m // 60}:{m % 60:02}:{s:02}" if m >= 60 else f"{m}:{s:02}"


def parse_formats(value: str) -> list[str]:
    fmts = [f.strip().lower() for f in value.split(",") if f.strip()]
    bad = [f for f in fmts if f not in FORMATS]
    if bad or not fmts:
        raise argparse.ArgumentTypeError(f"formats must be from {', '.join(FORMATS)}")
    return fmts


def main() -> None:
    ap = argparse.ArgumentParser(prog="mlx-transcribe", description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--format", type=parse_formats, default=["txt"],
                    help="comma-separated: txt, srt, json (default: txt)")
    ap.add_argument("--out", type=Path, help="output directory (default: next to each file)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--language", default="en", help="language code, or 'auto' to detect")
    ap.add_argument("--force", action="store_true", help="overwrite existing outputs")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--notify", action="store_true", help="post a macOS notification when done")
    ap.add_argument("--progress-window", action="store_true", help="show a floating progress bar")
    args = ap.parse_args()

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    todo = [f for f in args.files if args.force or not done_already(f, args)]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} to transcribe with {args.model}", flush=True)
    window = ProgressWindow() if args.progress_window and todo else None
    if args.notify and todo and not window:
        notify("Transcribing…", todo[0].name if len(todo) == 1 else f"{len(todo)} files")

    ok, failed = [], []
    try:
        for i, src in enumerate(todo, 1):
            out_dir = args.out or src.parent
            lock = out_dir / f".{src.stem}.lock"
            if (done_already(src, args) and not args.force) or not claim(lock):
                continue  # finished or claimed by another worker since we listed files
            try:
                transcribe_one(src, out_dir, args, f"{i}/{len(todo)}", window)
                ok.append(src)
            except Exception as e:  # keep going; one bad file shouldn't sink a batch
                print(f"[{i}/{len(todo)}] {src.name}: FAILED: {e}", file=sys.stderr, flush=True)
                failed.append(src)
            finally:
                lock.unlink(missing_ok=True)
    except KeyboardInterrupt:  # Ctrl-C or the window's Cancel; locks already released
        print("cancelled", file=sys.stderr, flush=True)
        if args.notify:
            notify("Transcription cancelled", f"{len(ok)} of {len(todo)} finished")
        sys.exit(130)
    finally:
        if window:
            window.close()

    if args.notify:
        if failed:
            notify("Transcription failed", ", ".join(f.name for f in failed), sound="Basso")
        elif ok:
            names = ok[0].name if len(ok) == 1 else f"{len(ok)} files"
            notify("Transcription done", f"{names} → {', '.join(args.format)}", sound="Glass")
    sys.exit(1 if failed else 0)


def done_already(src: Path, args: argparse.Namespace) -> bool:
    out_dir = args.out or src.parent
    return all((out_dir / f"{src.stem}.{fmt}").exists() for fmt in args.format)


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3_600_000:02}:{ms // 60_000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write(path: Path, text: str) -> None:
    """Write-then-rename so readers (e.g. an indexer) never see a partial file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    tmp.replace(path)


def transcribe_one(src: Path, out_dir: Path, args: argparse.Namespace, progress: str,
                   window: ProgressWindow | None = None) -> None:
    import mlx_whisper  # slow import; keep --help fast

    t0 = time.time()
    title = src.name if progress == "1/1" else f"({progress}) {src.name}"
    if window:
        window.update(-1, title, "Preparing…")

        def on_progress(done: int, total: int) -> None:
            frac = done / max(total, 1)
            took = time.time() - t0
            eta = f" · ~{clock(took / frac - took)} left" if frac > 0.02 else ""
            window.update(frac, title, f"{clock(done / FRAMES_PER_SEC)} / "
                          f"{clock(total / FRAMES_PER_SEC)} · {frac:.0%}{eta}")

        hook_progress(on_progress)
    result = mlx_whisper.transcribe(
        str(src),
        path_or_hf_repo=args.model,
        language=None if args.language == "auto" else args.language,
        condition_on_previous_text=False,  # avoids repetition loops on long audio
    )
    segs = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for s in result["segments"] if s["text"].strip()]

    if "txt" in args.format:
        write(out_dir / f"{src.stem}.txt", "\n".join(s["text"] for s in segs) + "\n")
    if "srt" in args.format:
        write(out_dir / f"{src.stem}.srt", "\n".join(
            f"{n}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n"
            for n, s in enumerate(segs, 1)))
    if "json" in args.format:
        rounded = [{**s, "start": round(s["start"], 1), "end": round(s["end"], 1)} for s in segs]
        write(out_dir / f"{src.stem}.json",
              json.dumps({"file": src.name, "model": args.model, "segments": rounded}))

    audio = segs[-1]["end"] if segs else 0
    took = time.time() - t0
    print(f"[{progress}] {src.name}: {audio/60:.0f} min audio in {took/60:.1f} min "
          f"({audio/max(took,1):.0f}x)", flush=True)
