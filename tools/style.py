"""Phase 3: Top-Clips der Kampagnen (campaign.references) analysieren -> docs/STYLE.md.

Nur zur Analyse (Länge, Tempo, Format, Titel-Muster, Views) – nichts wird übernommen, gepostet oder im Repo abgelegt.
Quelle: offizielle YouTube Data API (Secret YOUTUBE_API_KEY) – kein Download (YouTube sperrt Actions-IPs per Bot-Abfrage).
Nur Kampagnen mit Stream-/VOD-Quellen (wie unsere); nur Metadaten: Dauer, Views, Likes, Titel, Tags.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.llm import complete  # noqa: E402


def references(only: set[str], allow_all: bool, limit: int) -> list[str]:
    urls: list[str] = []
    for f in sorted(glob.glob(str(ROOT / "campaigns" / "cr-*.json"))):
        d = json.loads(Path(f).read_text())
        if only and d["id"] not in only:
            continue
        if not only and (d.get("source") or {}).get("type") not in ("vod", "channel", "stream", "clips"):
            continue                                   # nur Stream-Clip-Kampagnen, wie unsere
        for u in (d.get("references") or [])[:6]:      # max. 6 je Kampagne
            if allow_all or re.search(r"youtube\.com/(watch|shorts)|youtu\.be/", u):
                urls.append(u)
    return list(dict.fromkeys(urls))[:limit]


def api_stats(urls: list[str]) -> list[dict]:
    import os
    import urllib.parse
    import urllib.request
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        print("YOUTUBE_API_KEY fehlt")
        return []
    ids = list(dict.fromkeys(m.group(1) for u in urls if (m := re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", u))))
    rows = []
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "snippet,contentDetails,statistics", "id": ",".join(ids[i:i + 50]), "key": key})
        try:
            with urllib.request.urlopen("https://www.googleapis.com/youtube/v3/videos?" + q, timeout=30) as r:
                items = json.load(r).get("items", [])
        except Exception as e:  # noqa: BLE001
            print("  API-Fehler:", str(e)[:160])
            continue
        for it in items:
            m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", it["contentDetails"]["duration"])
            dur = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0) if m else 0
            sn, stt = it["snippet"], it.get("statistics", {})
            rows.append({"dur": dur, "views": int(stt.get("viewCount", 0)), "likes": int(stt.get("likeCount", 0)),
                         "title": sn.get("title", "")[:90], "title_words": len(sn.get("title", "").split()),
                         "tags": len(sn.get("tags") or []), "desc_len": len(sn.get("description", ""))})
    return [r for r in rows if 5 <= r["dur"] <= 180]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-videos", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--campaigns", default="")
    a = ap.parse_args()
    urls = references({c for c in a.campaigns.split(",") if c}, a.all, a.max_videos)
    print(f"{len(urls)} Referenzen")
    rows = api_stats(urls)
    print(f"{len(rows)} analysiert")
    if len(rows) < 5:
        print("Zu wenige Daten – STYLE.md nicht geschrieben.")
        return 1
    rows.sort(key=lambda r: r["views"], reverse=True)
    top = rows[: max(5, len(rows) // 3)]

    def med(k, rs):
        v = [r[k] for r in rs if r.get(k) is not None]
        return round(st.median(v), 1) if v else None

    stats = {k: {"alle": med(k, rows), "top_drittel": med(k, top)} for k in ("dur", "title_words", "tags", "views", "likes")}
    titles = [r["title"] for r in top][:15]       # nur als LLM-Eingabe, nicht gespeichert
    prompt = ("Kurzvideo-Referenzen (Top-Drittel nach Views) und Kennzahlen. Leite knappe, konkrete Regeln für Stream-Clips ab "
              "(Länge, Titel-Muster, Hook-Wortwahl, Tags). Nur Stichpunkte, deutsch, keine Zitate der Titel.\n"
              f"Kennzahlen (Median alle vs. Top): {json.dumps(stats)}\nTitel Top: {titles}")
    rules = complete(prompt, system="Du bist Short-Form-Analyst. Antworte nur mit einer Markdown-Liste.", task="style_rules")
    md = ["# Stil-Regeln aus Referenz-Clips (automatisch, tools/style.py)", "",
          f"Basis: {len(rows)} analysierte Referenzen, davon Top-Drittel = {len(top)}. Nur Kennzahlen, keine Links/Accounts.", "",
          "## Kennzahlen (Median)", "| Maß | alle | Top-Drittel |", "|---|---|---|"]
    md += [f"| {k} | {v['alle']} | {v['top_drittel']} |" for k, v in stats.items()]
    md += ["", "## Regeln (LLM-Auswertung, prüfen)", str(rules).strip(), ""]
    (ROOT / "docs" / "STYLE.md").write_text("\n".join(md))
    print("docs/STYLE.md geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
