"""Kampagnen prüfen, filtern, priorisieren.

    python tools/campaigns.py validate [dateien...]   # Vollständigkeit; Exit 1 bei Fehlern
    python tools/campaigns.py triage [--write]         # Status aktualisieren, filtern, ranken -> out/campaigns.md

Priorität (erwarteter Ertrag je Clip, gewichtet):
    pro_clip = min(rate_per_1k * est_views / 1000, max_payout_per_clip)
    * below_min_views_factor, falls est_views < min_views
    score = pro_clip * Restbudget-Anteil * (1 + preferred_bonus bei Wunsch-Streamer)
est_views: Kampagnenwert, sonst default_est_views (bis Phase 3 echte Daten liefert).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CDIR = ROOT / "campaigns"
PREFS = json.loads((ROOT / "config" / "preferences.json").read_text())
ACCOUNTS = json.loads((ROOT / "config" / "accounts.json").read_text())["accounts"]

PLATFORMS = {"tiktok", "youtube", "instagram", "x", "facebook"}
STATUSES = {"open", "paused", "ended", "stopped"}
REQUIRED = ["id", "title", "url", "status", "source", "platforms", "payment", "budget", "submission"]
RECOMMENDED = ["streamer", "language", "format", "required_tags", "hashtags", "disclosure", "rules", "deadline"]


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def load(paths=None) -> list[tuple[pathlib.Path, dict]]:
    files = [pathlib.Path(p) for p in paths] if paths else sorted(
        p for p in CDIR.glob("*.json") if not p.name.startswith("_"))
    return [(p, json.loads(p.read_text())) for p in files]


def validate(c: dict) -> tuple[list[str], list[str]]:
    err, warn = [], []
    for k in REQUIRED:
        if c.get(k) in (None, "", [], {}):
            err.append(f"fehlt: {k}")
    for k in RECOMMENDED:
        if c.get(k) in (None, "", [], {}):
            warn.append(f"leer: {k}")
    if c.get("status") and c["status"] not in STATUSES:
        err.append(f"status ungültig: {c['status']}")
    bad = set(c.get("platforms") or []) - PLATFORMS
    if bad:
        err.append(f"Plattform unbekannt: {sorted(bad)}")
    src = c.get("source") or {}
    if src:
        if src.get("type") not in PREFS["allowed_source_types"]:
            err.append(f"source.type ungültig: {src.get('type')}")
        if not src.get("urls"):
            err.append("source.urls leer")
        if not src.get("permission_quote"):
            err.append("source.permission_quote fehlt (keine Quelle ohne Freigabe)")
    pay = c.get("payment") or {}
    if pay:
        if pay.get("model") not in {"cpm", "per_post", "pool", "retainer"}:
            err.append(f"payment.model ungültig: {pay.get('model')}")
        if pay.get("model") == "cpm" and not pay.get("rate_per_1k"):
            err.append("payment.rate_per_1k fehlt")
        if pay.get("min_views") is None:
            warn.append("payment.min_views unbekannt")
    b = c.get("budget") or {}
    if b and (b.get("total") is None or b.get("remaining") is None):
        err.append("budget.total/remaining fehlt")
    if c.get("deadline"):
        try:
            dt.date.fromisoformat(c["deadline"])
        except ValueError:
            err.append("deadline kein ISO-Datum")
    if not c.get("verified"):
        warn.append("noch nicht von Hand bestätigt (verified=false)")
    if c.get("disclosure") in (None, ""):
        warn.append("Werbe-Hinweis unklar (CR: Hinweis muss am Videoanfang stehen)")
    return err, warn


def remaining_frac(c: dict) -> float:
    b = c.get("budget") or {}
    total, rem = b.get("total") or 0, b.get("remaining") or 0
    return max(0.0, min(1.0, rem / total)) if total else 0.0


def exclusion(c: dict, joining: bool) -> str | None:
    """Grund, warum die Kampagne nicht bearbeitet wird – oder None."""
    if c.get("status") != "open":
        return f"Status {c.get('status')}"
    if c.get("deadline") and dt.date.fromisoformat(c["deadline"]) < today():
        return "Frist abgelaufen"
    if remaining_frac(c) <= 0:
        return "Budget leer"
    if joining and remaining_frac(c) < PREFS["min_budget_remaining_for_join"]:
        return f"Restbudget {remaining_frac(c):.0%} < {PREFS['min_budget_remaining_for_join']:.0%} (Einstieg)"
    if (c.get("language") or "en") != PREFS["language"]:
        return f"Sprache {c.get('language')}"
    if (c.get("category") or "") in PREFS["excluded_categories"]:
        return f"Kategorie {c['category']}"
    text = " ".join(str(c.get(k, "")) for k in ("title", "brand", "description", "notes")).lower()
    hit = next((k for k in PREFS["excluded_keywords"] if k in text), None)
    if hit:
        return f"Ausschluss-Wort '{hit}'"
    src = c.get("source") or {}
    if not src.get("permission_quote"):
        return "Quellen-Freigabe fehlt"
    usable = set(c.get("platforms") or []) & active_platforms(c)
    if not usable:
        return "keine passenden aktiven Accounts"
    return None


def active_platforms(c: dict) -> set[str]:
    out = set()
    for a in ACCOUNTS:
        if not a["active"]:
            continue
        f = a.get("campaign_filter") or {}
        if f.get("include") and c.get("id") not in f["include"]:
            continue
        if c.get("id") in (f.get("exclude") or []):
            continue
        out.add(a["platform"])
    return out


def score(c: dict) -> float:
    pay = c.get("payment") or {}
    est = c.get("est_views") or PREFS["default_est_views"]
    if pay.get("model") == "per_post":
        per_clip = pay.get("amount_per_post") or 0
    else:
        per_clip = (pay.get("rate_per_1k") or 0) * est / 1000
    if pay.get("max_payout_per_clip"):
        per_clip = min(per_clip, pay["max_payout_per_clip"])
    if pay.get("min_views") and est < pay["min_views"]:
        per_clip *= PREFS["below_min_views_factor"]
    bonus = 1 + PREFS["preferred_bonus"] * any(
        s.lower() in (c.get("streamer") or "").lower() for s in PREFS["preferred_streamers"])
    return round(per_clip * remaining_frac(c) * bonus, 2)


def cmd_validate(paths) -> int:
    bad = 0
    for p, c in load(paths or None):
        err, warn = validate(c)
        bad += bool(err)
        print(f"{'FEHLER' if err else 'ok':6} {p.name}")
        for e in err:
            print(f"   ✗ {e}")
        for w in warn:
            print(f"   · {w}")
    return 1 if bad else 0


def cmd_triage(write: bool) -> int:
    active, join, skipped = [], [], []
    for p, c in load():
        # Automatisch stoppen: Frist vorbei oder Budget leer
        stop = None
        if c.get("status") == "open":
            if c.get("deadline") and dt.date.fromisoformat(c["deadline"]) < today():
                stop = "Frist abgelaufen"
            elif c.get("budget") and remaining_frac(c) <= 0:
                stop = "Budget leer"
        if stop:
            c["status"] = "stopped"
            c["notes"] = (c.get("notes", "") + f" [auto-stop {today()}: {stop}]").strip()
            if write:
                p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
        err, _ = validate(c)
        if err:
            skipped.append((c, "unvollständig: " + "; ".join(err[:2])))
            continue
        why = exclusion(c, joining=not c.get("joined"))
        if why:
            skipped.append((c, why))
        elif c.get("joined"):
            active.append(c)
        else:
            join.append(c)
    active.sort(key=score, reverse=True)
    join.sort(key=score, reverse=True)

    lines = [f"# Kampagnen {today()}", "", "## Bearbeiten (beigetreten, nach Priorität)"]
    lines += [f"- **{score(c)}** {c['title']} – {', '.join(sorted(set(c['platforms']) & active_platforms(c)))} "
              f"– Rest {remaining_frac(c):.0%}" for c in active] or ["- keine"]
    lines += ["", "## Beitreten (ein Klick)"]
    lines += [f"- [ ] **{score(c)}** [{c['title']}]({c['url']}) – Rest {remaining_frac(c):.0%}, "
              f"Frist {c.get('deadline') or '?'}" for c in join] or ["- keine"]
    lines += ["", "## Ausgeschlossen"]
    lines += [f"- {c.get('title', c.get('id'))}: {why}" for c, why in skipped] or ["- keine"]
    report = "\n".join(lines) + "\n"
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "campaigns.md").write_text(report)
    (out / "queue.json").write_text(json.dumps([c["id"] for c in active], indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(report)
    print(report)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "validate":
        sys.exit(cmd_validate(a[1:]))
    if a[0] == "triage":
        sys.exit(cmd_triage("--write" in a))
    sys.exit(__doc__)
