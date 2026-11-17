"""Daten fürs Projekt-Dashboard erzeugen (out/dashboard/*.json).

    python tools/dashboard_data.py [runs.json]

Enthält nur öffentliche Kampagnendaten und den Projektstand – keine Account-Daten.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import campaigns as cm  # noqa: E402

OUT = ROOT / "out" / "dashboard"

PHASES = [
    ("0", "Recherche", "fertig", "AGB, Plattform-APIs, Quellen geprüft"),
    ("1", "Kampagnen", "läuft", "Automatische Suche alle 3 Std., Filter, Rangliste, Beitritts-Issue"),
    ("2", "Clip-Fabrik", "offen", "Stream laden, Momente finden, 9:16-Schnitt, Untertitel, QA"),
    ("2b", "Hook", "offen", "Kaltstart, Hook-Text, 3 Varianten pro Clip"),
    ("3", "Qualität", "offen", "Referenz-Clips, STYLE.md, Testlauf, Feedback-Schleife"),
    ("4", "Posten & Einreichen", "offen", "YouTube/TikTok-Upload, Einreich-Liste (30-Min.-Frist)"),
    ("5", "Dauerbetrieb", "offen", "Täglicher Ablauf ohne Handarbeit"),
]


def reason_group(why: str) -> str:
    rules = [("Quelle", "keine Stream-/Video-Quelle"), ("Freigabe", "Quellen-Freigabe fehlt"),
             ("Restbudget", "Restbudget unter 50 %"), ("Sprache", "andere Sprache"),
             ("Kategorie", "Kategorie ausgeschlossen"), ("Ausschluss-Wort", "Ausschluss-Wort"),
             ("Accounts", "Plattform ohne Account"), ("Budget leer", "Budget leer"),
             ("Status", "beendet/pausiert"), ("unvollständig", "Daten unvollständig")]
    return next((label for key, label in rules if key in why), "sonstiges")


def main(runs_path: str | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, c in cm.load():
        err, _ = cm.validate(c)
        if not c.get("source"):
            why = "keine Stream-/Video-Quelle im Briefing"
        elif err:
            why = "unvollständig: " + err[0]
        else:
            why = cm.exclusion(c, joining=not c.get("joined")) or ""
        decision = "ausgeschlossen" if why else ("bearbeiten" if c.get("joined") else "beitreten")
        pay = c.get("payment") or {}
        st = c.get("stats") or {}
        rows.append({
            "kampagne": re.sub(r"\s+", " ", c.get("title") or c["id"]).strip(),
            "link": c.get("url"),
            "entscheidung": decision,
            "grund": reason_group(why) if why else "",
            "grund_detail": why,
            "punkte": cm.score(c) if not why else None,
            "modell": pay.get("model"),
            "rate_pro_1k": pay.get("rate_per_1k"),
            "restbudget_pct": round(cm.remaining_frac(c) * 100),
            "budget_usd": (c.get("budget") or {}).get("total"),
            "kategorie": c.get("category"),
            "plattformen": ", ".join(c.get("platforms") or []),
            "avg_views": st.get("avg_views"),
            "bewerbung": "ja" if c.get("requires_application") else "nein",
            "erfasst": c.get("captured_at"),
        })
    rows.sort(key=lambda r: (r["entscheidung"] != "bearbeiten", r["entscheidung"] != "beitreten",
                             -(r["punkte"] or 0), r["kampagne"]))
    (OUT / "kampagnen.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    (OUT / "phasen.json").write_text(json.dumps(
        [{"phase": p, "name": n, "status": s, "inhalt": d} for p, n, s, d in PHASES], indent=1, ensure_ascii=False))
    if runs_path:
        runs = json.loads(pathlib.Path(runs_path).read_text())
        (OUT / "laeufe.json").write_text(json.dumps(runs, indent=1, ensure_ascii=False))
    print(f"{len(rows)} Kampagnen -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
