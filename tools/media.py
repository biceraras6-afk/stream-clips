"""ffmpeg/yt-dlp-Helfer für die Clip-Fabrik."""
from __future__ import annotations

import json
import math
import re
import subprocess
import wave
from pathlib import Path

import numpy as np


def run(cmd: list[str], capture: bool = False, check: bool = True) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0 and not (cmd[0] == "yt-dlp" and "-J" in cmd and r.stdout.strip().startswith("{")):
        raise RuntimeError(f"{cmd[0]} fehlgeschlagen: {r.stderr[-1500:]}")
    return (r.stdout + r.stderr) if capture else r.stdout


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    return json.loads(out)


def video_info(path: Path) -> dict:
    p = probe(path)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": float(num) / float(den or 1),
            "duration": float(p["format"].get("duration", 0))}


# ---------- Quellen ----------

SINGLE_VIDEO = re.compile(
    r"(twitch\.tv/videos/\d+|youtube\.com/watch|youtu\.be/|youtube\.com/live/|kick\.com/[^/]+/videos?/|kick\.com/video/)")


def ytdlp_json(url: str, extra: list[str] | None = None) -> dict:
    return json.loads(run(["yt-dlp", "-J", "--no-warnings", *(extra or []), url]))


def resolve_source(url: str, seen: set[str], limit: int = 5) -> dict | None:
    """Kanal-URL -> neuestes noch nicht verarbeitetes Video; Einzelvideo -> sich selbst."""
    if SINGLE_VIDEO.search(url):
        meta = ytdlp_json(url)
        return None if meta["id"] in seen else meta
    base = url.rstrip("/")
    candidates = [url]
    if "twitch.tv/" in url:
        name = base.split("twitch.tv/")[1].split("/")[0]
        candidates = [f"https://www.twitch.tv/{name}/videos?filter=archives&sort=time",
                      f"https://www.twitch.tv/{name}/videos?filter=all&sort=time",
                      f"https://www.twitch.tv/{name}/clips?filter=clips&range=7d"]
    elif "youtube.com/" in url and "/@" in url:
        base = re.sub(r"/(videos|streams|shorts)/?$", "", base)
        candidates = [base + "/streams", base + "/videos"]
    elif "kick.com/" in url:
        name = base.split("kick.com/")[1].split("/")[0]
        candidates = [f"https://kick.com/{name}/videos", f"https://kick.com/{name}"]
    for cand in candidates:
        try:
            pl = ytdlp_json(cand, ["--flat-playlist", "--playlist-items", f"1:{limit}"])
        except RuntimeError as e:
            print(f"  Liste {cand}: {str(e)[-200:]}")
            continue
        entries = [e for e in (pl.get("entries") or []) if e]
        if not entries and pl.get("_type") != "playlist" and pl.get("id"):
            entries = [pl]                                   # Einzelvideo/Live statt Liste
        print(f"  Liste {cand}: {len(entries)} Einträge")
        for e in entries:
            if e.get("id") and e["id"] not in seen and not e.get("is_live"):
                try:
                    return ytdlp_json(e.get("url") or e.get("webpage_url") or e["id"])
                except RuntimeError as err:
                    print(f"  Video {e.get('id')}: {str(err)[-200:]}")
    return None


def download_audio(url: str, out_wav: Path) -> Path:
    tmp = out_wav.with_suffix(".src")
    run(["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio/best", "-o", str(tmp) + ".%(ext)s", url])
    src = next(out_wav.parent.glob(tmp.name + ".*"))
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000", str(out_wav)])
    src.unlink()
    return out_wav


def download_section(url: str, start: float, end: float, out: Path, max_h: int = 1080) -> Path:
    run(["yt-dlp", "-q", "--no-warnings", "-f", f"bv*[height<={max_h}]+ba/b[height<={max_h}]",
         "--download-sections", f"*{start:.2f}-{end:.2f}", "--force-keyframes-at-cuts",
         "--merge-output-format", "mp4", "-o", str(out), url])
    return out


# ---------- Audio-Signale ----------

def loudness_curve(wav: Path, hop: float = 1.0) -> np.ndarray:
    """RMS in dBFS je `hop` Sekunden."""
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * hop)
    frames = data[: len(data) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(rms)


def measure_loudness(path: Path) -> dict:
    out = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
              capture=True)
    j = json.loads(out[out.rindex("{"): out.rindex("}") + 1])
    return {k: float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


def normalize_audio(src: Path, dst: Path, target: float, tp: float) -> Path:
    m = measure_loudness(src)
    af = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "copy", "-af", af, "-ar", "48000",
         "-c:a", "aac", "-b:a", "192k", str(dst)])
    return dst


def black_segments(path: Path, min_d: float = 0.4) -> list[tuple[float, float]]:
    out = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"blackdetect=d={min_d}:pix_th=0.10",
               "-an", "-f", "null", "-"], capture=True)
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", out)]


def db(x: float) -> float:
    return 20 * math.log10(max(x, 1e-9))
