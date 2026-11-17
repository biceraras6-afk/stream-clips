"""Automatische Qualitätsprüfung je Clip. Nur "pass" geht weiter."""
from __future__ import annotations

import json
from pathlib import Path

from tools import media

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "factory.json").read_text())


def check(clip_dir: Path, post: dict, campaign: dict, n_words: int, n_caption_words: int,
          min_s: int, max_s: int) -> dict:
    res: list[dict] = []

    def add(name, ok, detail=""):
        res.append({"check": name, "ok": bool(ok), "detail": detail})

    mp4 = clip_dir / "clip.mp4"
    info = media.video_info(mp4)
    o = CFG["output"]
    add("Format 1080x1920", (info["w"], info["h"]) == (o["width"], o["height"]), f"{info['w']}x{info['h']}")
    add("Länge", min_s - 1 <= info["duration"] <= max_s + 1, f"{info['duration']:.1f}s (Soll {min_s}-{max_s})")
    lo = media.measure_loudness(mp4)
    t = CFG["loudness"]
    add("Lautheit −14 LUFS", abs(lo["input_i"] - t["target"]) <= t["tolerance"], f"{lo['input_i']:.1f} LUFS")
    add("True Peak", lo["input_tp"] <= t["true_peak"] + 0.5, f"{lo['input_tp']:.1f} dBTP")
    cov = n_caption_words / max(1, n_words)
    add("Untertitel-Abdeckung", cov >= 0.95, f"{cov:.0%}")
    blacks = media.black_segments(mp4)
    add("Kein schwarzes Bild", not blacks, f"{len(blacks)} Stellen" if blacks else "")
    add("Erstes Bild nicht schwarz", not any(a < 0.2 for a, _ in blacks))
    texts = " ".join(json.dumps(v) for v in post["platforms"].values()).lower()
    missing = [x for x in post["required_tags"] + post["hashtags"] if x.lower() not in texts]
    add("Pflicht-Tags in allen Texten", not missing, ", ".join(missing))
    if campaign.get("disclosure"):
        add("Werbe-Hinweis am Anfang", (clip_dir / "subs.ass").read_text().count(",Ad,") > 0)
    need = set(campaign.get("platforms") or [])
    add("Text je Plattform", need <= set(post["platforms"]), ", ".join(sorted(need - set(post["platforms"]))))
    req = campaign.get("requirements") or {}
    if req.get("brandLogo") or (campaign.get("content_rules") or {}).get("branding", {}).get("logoRequired"):
        add("Logo eingeblendet", False, "Kampagne verlangt Logo – noch nicht unterstützt")
    if req.get("faceOnCamera"):
        add("Eigenes Gesicht im Video", False, "Kampagne verlangt Face-Cam des Clippers")
    ok = all(r["ok"] for r in res)
    out = {"status": "pass" if ok else "fail", "checks": res}
    (clip_dir / "qa.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out
