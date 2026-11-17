"""Kampagnen auf Content Rewards automatisch finden und aktualisieren.

Nur öffentliche Seiten (ohne Login), robots.txt wird geprüft, `/api/` nie genutzt,
langsamer Abruf (Pause zwischen Seiten), eindeutiger User-Agent.

    python tools/discover.py            # Liste + Details holen, campaigns/cr-*.json schreiben
    python tools/discover.py --dry-run  # nur anzeigen

Ablauf:
1. Öffentliche Kampagnenliste (/c/discover/clipping) + Sitemap (neue Einträge) lesen.
2. Vorfilter (Plattformen, Kategorie, Restbudget, Ausschlusswörter) – spart Abrufe.
3. Detailseite je Kandidat: Raten je Plattform, Mindest-/Höchstauszahlung, Budget, Status,
   Briefing, Pflicht-Flags, Top-Clips.
4. Briefing per Gemini/Groq in Felder übersetzen (nur bei Änderung).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import campaigns as cm  # noqa: E402
from tools.llm import LLMError, complete  # noqa: E402

BASE = "https://contentrewards.com"
UA = "stream-clips-bot/0.1 (personal campaign finder; respects robots.txt)"
DELAY = 4.0
MAX_DETAILS = 30
LIST_PAGES = ["/c/discover/clipping", "/c/discover"]
PREFS = cm.PREFS

_robots = urllib.robotparser.RobotFileParser(BASE + "/robots.txt")
_last = 0.0


def fetch(path: str) -> str:
    global _last
    url = path if path.startswith("http") else BASE + path
    if "/api/" in url or not _robots.can_fetch(UA, url):
        raise PermissionError(f"robots.txt verbietet {url}")
    wait = DELAY - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def rsc(html: str) -> str:
    """Next.js-Datenstrom aus der Seite zusammensetzen."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def _decode_after(s: str, marker: str):
    dec = json.JSONDecoder()
    for m in re.finditer(re.escape(marker), s):
        try:
            yield dec.raw_decode(s, m.end())[0]
        except json.JSONDecodeError:
            continue


# ---------- Liste ----------

def list_campaigns() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for page in LIST_PAGES:
        try:
            s = rsc(fetch(page))
        except (urllib.error.URLError, PermissionError) as e:
            print(f"Liste {page}: {e}")
            continue
        for results in _decode_after(s, '"initialResults":'):
            for block in results if isinstance(results, list) else []:
                for c in block.get("campaigns", []):
                    out.setdefault(c["id"], c)
    return out


def sitemap_recent(days: int = 7) -> list[str]:
    try:
        xml = fetch("/sitemap.xml")
    except (urllib.error.URLError, PermissionError):
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    ids = []
    for loc, mod in re.findall(r"<loc>[^<]*/c/campaigns/([0-9a-f-]{36})</loc>\s*<lastmod>([^<]+)</lastmod>", xml):
        try:
            if dt.datetime.fromisoformat(mod.replace("Z", "+00:00")) >= cutoff:
                ids.append(loc)
        except ValueError:
            pass
    return ids


def prefilter(item: dict, known: dict) -> str | None:
    """Grund zum Überspringen (ohne Detailabruf) – oder None."""
    if item.get("type") not in ("cpm", "pool"):
        return f"Typ {item.get('type')}"
    if not set(item.get("platforms") or []) & {a["platform"] for a in cm.ACCOUNTS if a["active"]}:
        return "Plattformen"
    if item.get("category") not in PREFS["cr_categories"]:
        return f"Kategorie {item.get('category')}"
    text = f"{item.get('title', '')} {item.get('brand', '')} {item.get('description', '')}".lower()
    hit = next((k for k in PREFS["excluded_keywords"] if k in text), None)
    if hit:
        return f"Ausschluss-Wort '{hit}'"
    total = item.get("budgetTotalRaw") or 0
    frac = (item.get("availableBudgetRaw") or 0) / total if total else 0
    joined = known.get(item["id"], {}).get("joined")
    if frac <= 0 or (not joined and frac < PREFS["min_budget_remaining_for_join"]):
        return f"Restbudget {frac:.0%}"
    return None


# ---------- Detail ----------

def detail(cr_id: str) -> dict | None:
    s = rsc(fetch(f"/c/campaigns/{cr_id}"))
    full, summary = None, None
    for o in _decode_after(s, '"state":{"data":'):
        if not isinstance(o, dict) or o.get("id") != cr_id:
            continue
        if "configuration" in o:
            full = o
        if "payouts" in o:
            summary = o
    if not (full or summary):
        return None
    return {"full": full or {}, "summary": summary or {}}


def to_campaign(cr_id: str, d: dict, old: dict) -> dict:
    f, s = d["full"], d["summary"]
    conf = f.get("configuration") or {}
    content = conf.get("content") or {}
    req = conf.get("requirement") or {}
    metrics = s.get("metrics") or f.get("metrics") or {}
    name = (s.get("name") or f.get("name") or "").replace("$$", "$")
    budget = (s.get("budgetCents") or conf.get("budget") or 0) / 100
    spent = (metrics.get("budgetSpentCents") or 0) / 100
    payouts = s.get("payouts") or [
        {"platform": p["platform"], "rateCents": p.get("rate"), "minPayoutCents": p.get("minPayout"),
         "maxPayoutCents": p.get("maxPayout"), "payoutType": f.get("type")}
        for p in conf.get("payoutModel") or []]
    ours = {a["platform"] for a in cm.ACCOUNTS if a["active"]}
    per_platform = {p["platform"]: {"rate_per_1k": (p.get("rateCents") or 0) / 100,
                                    "min_payout": (p.get("minPayoutCents") or 0) / 100 or None,
                                    "max_payout_per_clip": (p.get("maxPayoutCents") or 0) / 100 or None}
                    for p in payouts}
    best = max((v for k, v in per_platform.items() if k in ours), key=lambda v: v["rate_per_1k"],
               default={"rate_per_1k": None, "min_payout": None, "max_payout_per_clip": None})
    min_views = (round(best["min_payout"] / best["rate_per_1k"] * 1000)
                 if best["min_payout"] and best["rate_per_1k"] else None)
    approved = int(metrics.get("approvedSubmissionCount") or 0)
    views = int(metrics.get("totalViews") or 0)
    status = {"active": "open", "paused": "paused"}.get(s.get("status") or f.get("status"), "ended")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]

    c = {**{k: None for k in cm_template()}, **old}
    c.update({
        "id": old.get("id") or f"cr-{cr_id[:8]}-{slug}",
        "cr_id": cr_id,
        "title": name,
        "url": f"{BASE}/c/campaigns/{cr_id}",
        "status": status,
        "brand": (f.get("organization") or {}).get("name") or s.get("organizationName"),
        "category": ((s.get("categories") or content.get("contentCategories") or [{}])[0]).get("id"),
        "description": s.get("description") or f.get("description") or "",
        "guidelines": content.get("guidelines") or "",
        "platforms": sorted(s.get("platforms") or per_platform),
        "payment": {"model": {"perPost": "per_post", "per-post": "per_post"}.get(
                        s.get("payoutType") or f.get("type"), s.get("payoutType") or f.get("type")),
                    "amount_per_post": max(((p.get("amountCents") or 0) / 100 for p in payouts), default=0) or None, "rate_per_1k": best["rate_per_1k"],
                    "min_payout": best["min_payout"], "max_payout_per_clip": best["max_payout_per_clip"],
                    "min_views": min_views, "per_platform": per_platform, "geo_priced": s.get("geoPriced")},
        "budget": {"total": budget, "remaining": round(max(0.0, budget - spent), 2), "currency": "USD",
                   "updated_at": dt.date.today().isoformat()},
        "requires_application": bool(s.get("requiresApplication") or f.get("requiresApplication")),
        "requirements": {k: req.get(k) for k in ("oauthRequired", "oauthPlatforms", "linkInBio", "brandLogo",
                                                  "faceOnCamera", "preApproval", "draftCaptionRequired")},
        "content_rules": conf.get("rules") or {},
        "prepost_review": bool(req.get("preApproval")),
        "submission": {"method": "manual", "window_minutes": 30},
        "stats": {"approved": approved, "total_views": views, "creators": metrics.get("creatorCount"),
                  "avg_views": round(views / approved) if approved else None,
                  "avg_payout": round(spent / approved, 2) if approved else None,
                  "updated_at": metrics.get("metricsUpdatedAt")},
        "references": [t.get("postUrl") for t in metrics.get("topClips") or [] if t.get("postUrl")][:20],
        "locked_references": f.get("lockedReferences") or s.get("lockedReferences"),
        "launched_at": s.get("launchDate") or f.get("launchDate"),
        "joined": bool(old.get("joined")),
        "captured_at": old.get("captured_at") or dt.date.today().isoformat(),
    })
    return c


def cm_template() -> dict:
    return json.loads((ROOT / "campaigns" / "_example.json").read_text())


ENRICH_SYSTEM = (
    "You read a clipping campaign brief and return ONLY JSON with keys: "
    "streamer (main creator name or null), language (ISO 639-1 of the content to clip), "
    "source {type: one of vod|stream|drive|channel|clips, urls: [footage URLs named in the brief], "
    "permission_quote: the verbatim sentence that tells clippers which footage to clip, or null}, "
    "format {min_seconds, max_seconds, aspect}, required_tags [@handles required in caption], "
    "hashtags [required #tags], links [links required in caption/bio], disclosure (required ad label or null), "
    "rules {do: [...], dont: [...]} (short imperative phrases), overlays_allowed (bool or null), "
    "audience (e.g. '60%+ US' or null), flags {gambling, crypto, adult, political} as booleans. "
    "Never invent values; use null or [] when not stated."
)


STREAM_HINT = re.compile(r"twitch|kick\.com|\bkick\b|youtube|stream|vod|podcast|broadcast|livestream|episode", re.I)


def enrich(c: dict) -> dict:
    text = f"Title: {c['title']}\nDescription:\n{c['description']}\nGuidelines:\n{c['guidelines']}"
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    if c.get("brief_hash") == h and (c.get("source") or c.get("enriched")):
        return c
    # Gratis-Kontingent sparen: LLM nur, wenn das Briefing nach Stream/Video-Quelle klingt
    if not STREAM_HINT.search(text):
        c["brief_hash"] = h
        c["source"] = None
        return c
    try:
        e = complete(text[:20000], system=ENRICH_SYSTEM, task="campaign_enrich", json_mode=True, max_tokens=2048)
    except LLMError as err:
        print(f"  LLM nicht verfügbar ({err}) – Heuristik")
        e = heuristic(text)
    for k in ("streamer", "language", "source", "format", "required_tags", "hashtags", "links",
              "disclosure", "rules", "overlays_allowed", "audience", "flags"):
        if e.get(k) not in (None, "", [], {}):
            c[k] = e[k]
    flags = e.get("flags") or {}
    if any(flags.get(k) for k in ("gambling", "crypto", "adult")):
        c["category"] = next(k for k in ("gambling", "crypto", "adult") if flags.get(k))
    if flags.get("political"):
        c["category"] = "political"
    c["brief_hash"] = h
    c["enriched"] = "heuristic" not in e
    return c


def heuristic(text: str) -> dict:
    urls = re.findall(r"https?://(?:www\.)?(?:twitch\.tv|kick\.com|youtube\.com|youtu\.be|drive\.google\.com)/\S+", text)
    urls += ["https://" + u for u in re.findall(r"\b(?:twitch\.tv|kick\.com)/[\w-]+", text)]
    quote = next((ln.strip() for ln in text.splitlines() if re.search(r"\bclip", ln, re.I)
                  and re.search(r"twitch|kick|youtube|stream|broadcast|vod", ln, re.I)), None)
    return {"source": {"type": "vod", "urls": sorted(set(urls)), "permission_quote": quote} if urls else None,
            "required_tags": sorted(set(re.findall(r"(?<!\w)@[\w.]{2,}", text))),
            "hashtags": sorted(set(re.findall(r"(?<!\w)#\w{2,}", text))), "heuristic": True}


# ---------- Hauptlauf ----------

def main(dry: bool = False) -> int:
    _robots.read()
    known = {}
    for p, c in cm.load():
        if c.get("cr_id"):
            known[c["cr_id"]] = c
    items = list_campaigns()
    print(f"Liste: {len(items)} Kampagnen")
    todo, skipped = [], 0
    for cid, it in items.items():
        why = prefilter(it, known)
        if why:
            skipped += 1
        else:
            todo.append(cid)
    new_from_sitemap = [i for i in sitemap_recent() if i not in items and i not in known]
    # Reihenfolge: neue zuerst, dann beigetretene, dann bekannte offene
    todo = ([i for i in todo if i not in known] + new_from_sitemap
            + [i for i, c in known.items() if c.get("joined") and c.get("status") == "open"]
            + [i for i in todo if i in known])
    todo = list(dict.fromkeys(todo))[:MAX_DETAILS]
    print(f"Vorfilter: {skipped} übersprungen, {len(todo)} Detailseiten")
    changed = 0
    for cid in todo:
        try:
            d = detail(cid)
        except (urllib.error.URLError, PermissionError, TimeoutError) as e:
            print(f"  {cid}: {e}")
            continue
        if not d:
            print(f"  {cid}: keine Daten (Seitenaufbau geändert?)")
            continue
        old = known.get(cid, {})
        c = enrich(to_campaign(cid, d, old))
        tag = "neu" if not old else "akt"
        print(f"  [{tag}] {c['title'][:60]} – {c['status']}, Rest {cm.remaining_frac(c):.0%}")
        if not dry:
            (ROOT / "campaigns" / f"{c['id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
            changed += 1
    # bekannte Kampagnen, die nicht mehr gelistet sind und nicht abgerufen wurden: nichts ändern
    print(f"geschrieben: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
