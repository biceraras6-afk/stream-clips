"""Phase 3: Top-Clips der Kampagnen (campaign.references) analysieren -> docs/STYLE.md.

Nur zur Analyse (Länge, Tempo, Format, Titel-Muster, Views) – nichts wird übernommen, gepostet oder im Repo abgelegt.
Standard: nur YouTube-Referenzen (stabil). --all versucht auch TikTok/Instagram (fragil, Fehler werden übersprungen).
Ausgabe enthält nur Kennzahlen und Regeln, keine Links/Accounts/Titel.

Aufruf: python tools/style.py [--max-videos 40] [--all] [--campaigns id1,id2]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import statistics as st
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import media  # noqa: E402
from tools.llm import complete  # noqa: E402


def references(only: set[str], allow_all: bool, limit: int) -> list[str]:
    urls: list[str] = []
    for f in sorted(glob.glob(str(ROOT / "campaigns" / "cr-*.json"))):
        d = json.loads(Path(f).read_text())
        if only and d["id"] not in only:
            continue
        for u in (d.get("references") or [])[:3]:      # max. 3 je Kampagne -> Vielfalt
            if allow_all or re.search(r"youtube\.com/(watch|shorts)|youtu\.be/", u):
                urls.append(u)
    return list(dict.fromkeys(urls))[:limit]


def scene_cuts(path: Path, upto: float | None = None) -> list[float]:
    cmd = ["ffmpeg", "-hide_banner", "-i", str(path)] + (["-t", str(upto)] if upto else []) + \
          ["-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"]
    err = media.run(cmd, capture=True, check=False)
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", err)]


def analyze(url: str, tmp: Path) -> dict | None:
    try:
        meta = media.ytdlp_json(url)
    except Exception:  # noqa: BLE001
        return None
    dur = meta.get("duration") or 0
    if not dur or dur > 180:
        return None
    out = tmp / "v.mp4"
    try:
        media.run(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=480]+ba/b[height<=480]",
                   "--merge-output-format", "mp4", "-o", str(out), url])
        info = media.video_info(out)
        cuts = scene_cuts(out)
        lo = media.measure_loudness(out)
    except Exception:  # noqa: BLE001
        return None
    finally:
        for f in tmp.glob("v.*"):
            f.unlink()
    views = meta.get("view_count") or 0
    return {"dur": round(dur, 1), "w": meta.get("width") or info["w"], "h": meta.get("height") or info["h"],
            "views": views, "likes": meta.get("like_count") or 0, "title_words": len((meta.get("title") or "").split()),
            "title": (meta.get("title") or "")[:90], "cuts": len(cuts), "cuts_per_10s": round(len(cuts) / dur * 10, 1),
            "cuts_first3s": sum(1 for c in cuts if c <= 3.0), "loudness": lo.get("input_i") if isinstance(lo, dict) else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-videos", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--campaigns", default="")
    a = ap.parse_args()
    urls = references({c for c in a.campaigns.split(",") if c}, a.all, a.max_videos)
    print(f"{len(urls)} Referenzen")
    rows = []
    with tempfile.TemporaryDirectory() as t:
        for u in urls:
            r = analyze(u, Path(t))
            if r:
                rows.append(r)
    print(f"{len(rows)} analysiert")
    if len(rows) < 5:
        print("Zu wenige Daten – STYLE.md nicht geschrieben.")
        return 1
    rows.sort(key=lambda r: r["views"], reverse=True)
    top = rows[: max(5, len(rows) // 3)]

    def med(k, rs):
        v = [r[k] for r in rs if r.get(k) is not None]
        return round(st.median(v), 1) if v else None

    stats = {k: {"alle": med(k, rows), "top_drittel": med(k, top)} for k in ("dur", "cuts_per_10s", "cuts_first3s", "title_words", "views")}
    vertical = round(sum(r["h"] > r["w"] for r in top) / len(top), 2)
    titles = [r["title"] for r in top][:15]       # nur als LLM-Eingabe, nicht gespeichert
    prompt = ("Kurzvideo-Referenzen (Top-Drittel nach Views) und Kennzahlen. Leite knappe, konkrete Regeln für Stream-Clips ab "
              "(Länge, Schnitttempo, Hook in ersten 3 s, Titel-Muster, Format). Nur Stichpunkte, deutsch, keine Zitate der Titel.\n"
              f"Kennzahlen (Median alle vs. Top): {json.dumps(stats)}\nAnteil 9:16 im Top: {vertical}\nTitel Top: {titles}")
    rules = complete(prompt, system="Du bist Short-Form-Analyst. Antworte nur mit einer Markdown-Liste.", task="style_rules")
    md = ["# Stil-Regeln aus Referenz-Clips (automatisch, tools/style.py)", "",
          f"Basis: {len(rows)} analysierte Referenzen, davon Top-Drittel = {len(top)}. Nur Kennzahlen, keine Links/Accounts.", "",
          "## Kennzahlen (Median)", "| Maß | alle | Top-Drittel |", "|---|---|---|"]
    md += [f"| {k} | {v['alle']} | {v['top_drittel']} |" for k, v in stats.items()]
    md += [f"| Anteil 9:16 | – | {vertical} |", "", "## Regeln (LLM-Auswertung, prüfen)", str(rules).strip(), ""]
    (ROOT / "docs" / "STYLE.md").write_text("\n".join(md))
    print("docs/STYLE.md geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
