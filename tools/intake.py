"""Kampagne aus kopiertem Seitentext erfassen (Halbautomat).

Ablauf: Kampagnenseite auf Content Rewards öffnen -> Text kopieren -> Issue „Neue Kampagne“
(oder lokal: python tools/intake.py <url> < seite.txt). Gemini/Groq extrahiert die Felder,
das Skript schreibt campaigns/<id>.json (verified=false) und prüft auf Vollständigkeit.
Kein Abruf der CR-Seite durch das Skript (AGB-/robots-Lage, siehe docs/RESEARCH.md).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import campaigns  # noqa: E402
from tools.llm import LLMError, complete  # noqa: E402

TEMPLATE = json.loads((ROOT / "campaigns" / "_example.json").read_text())

SYSTEM = (
    "You extract structured data from a Content Rewards clipping campaign page. "
    "Return ONLY JSON matching the given template keys. Use null/[] when a value is not stated. "
    "Never invent values. Platforms lowercase from: tiktok, youtube, instagram, x, facebook. "
    "source.type one of: vod, stream, drive, channel, clips. "
    "source.permission_quote = verbatim sentence from the page that provides/permits the footage, else null. "
    "payment.model one of cpm, per_post, pool, retainer. Money as numbers in USD. Dates ISO YYYY-MM-DD. "
    "category: one of streamer, gaming, music, brand, gambling, casino, crypto, adult, political, other."
)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "campaign"


def extract(url: str, text: str) -> dict:
    tpl = {k: v for k, v in TEMPLATE.items() if k not in ("verified", "joined", "captured_at", "est_views")}
    prompt = f"Template:\n{json.dumps(tpl, indent=1)}\n\nURL: {url}\n\nPage text:\n{text[:30000]}"
    return complete(prompt, system=SYSTEM, task="campaign_intake", json_mode=True, max_tokens=4096)


def main(url: str, text: str, joined: bool = False) -> pathlib.Path:
    try:
        data = extract(url, text)
    except LLMError as e:
        print(f"LLM nicht verfügbar ({e}) – lege Gerüst zum Ausfüllen an.")
        data = {k: None for k in TEMPLATE}
        data["notes"] = text[:5000]
    c = {**{k: None for k in TEMPLATE}, **data}
    c["url"] = url
    c["id"] = slug(c.get("id") or c.get("title") or url.rstrip("/").split("/")[-1])
    c["status"] = c.get("status") or "open"
    c["submission"] = c.get("submission") or {"method": "manual", "window_minutes": 30}
    c.update(joined=joined, verified=False, est_views=None,
             captured_at=dt.datetime.now(dt.timezone.utc).date().isoformat())
    path = ROOT / "campaigns" / f"{c['id']}.json"
    if path.exists():  # bestehende Handangaben behalten
        old = json.loads(path.read_text())
        for k in ("joined", "verified", "est_views", "notes"):
            if old.get(k):
                c[k] = old[k]
    path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
    print(f"geschrieben: campaigns/{path.name}")
    campaigns.cmd_validate([str(path)])
    return path


def parse_issue(body: str) -> tuple[str, str, bool]:
    """Issue-Formular: Abschnitte '### <Label>' -> Werte."""
    parts = dict(re.findall(r"^### (.+?)\n+(.*?)(?=^### |\Z)", body, flags=re.S | re.M))
    get = lambda key: next((v.strip() for k, v in parts.items() if key in k.lower()), "")
    return get("link"), get("seitentext"), "[x]" in get("beigetreten").lower()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--issue":  # in GitHub Actions: Body aus Umgebungsvariable
        import os
        url, text, joined = parse_issue(os.environ["ISSUE_BODY"])
        if not url.startswith("https://"):
            sys.exit("Kampagnen-Link fehlt")
        main(url, text, joined)
    else:
        main(sys.argv[1], sys.stdin.read(), joined="--joined" in sys.argv)
