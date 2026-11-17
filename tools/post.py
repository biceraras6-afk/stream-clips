"""Posten + Einreich-Liste (Phase 4). Läuft stündlich in GitHub Actions (post.yml).

Ablauf je Lauf:
1. Fällige Slots je Account bestimmen (config/posting.json, Tageslimit = Anzahl Slots).
2. Neue Clip-Artefakte indexieren (nur QA "pass").
3. Pro fälligem Slot den besten passenden Clip wählen:
   Kampagne beigetreten + offen, Plattform verlangt, Account-Filter passt,
   noch nie auf dieser Plattform gepostet (kein Clip doppelt auf zwei Accounts derselben Plattform).
4. Erst Reservierung ins private Daten-Repo schreiben, dann hochladen -> nichts wird doppelt gepostet.
5. Issue im privaten Daten-Repo: „Jetzt einreichen“ mit Post-Link, Kampagnen-Link, Text (Push aufs Handy).
6. Geschlossene Issues = eingereicht -> Protokoll aktualisieren.

Protokoll: <data_repo>/posted.json und days/<datum>/posted.json (privat, nie im öffentlichen Repo).
DRY_RUN=1 -> nur Plan anzeigen.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import ghapi, platforms  # noqa: E402
from tools import campaigns as cm  # noqa: E402

CFG = json.loads((ROOT / "config" / "posting.json").read_text())
DATA = CFG["data_repo"]
TZ = ZoneInfo(CFG["timezone"])
DRY = os.environ.get("DRY_RUN") == "1"


def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def due_slots(posted: dict) -> list[tuple[dict, str]]:
    n = now()
    today = n.date().isoformat()
    out = []
    for a in cm.ACCOUNTS:
        if not a["active"]:
            continue
        for slot in CFG["slots"].get(a["platform"], []):
            h, m = map(int, slot.split(":"))
            t = n.replace(hour=h, minute=m, second=0, microsecond=0)
            if t <= n < t + dt.timedelta(minutes=CFG["slot_window_minutes"]):
                if f"{a['id']}|{today}|{slot}" not in posted["slots"]:
                    out.append((a, slot))
    return out


def index_artifacts(index: dict) -> bool:
    changed = False
    for art in ghapi.clip_artifacts():
        if str(art["id"]) in index["artifacts"]:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            names = ghapi.download_artifact(art, tmp)
            for n in names:
                if not n.endswith("post.json"):
                    continue
                d = Path(tmp) / Path(n).parent
                qa = json.loads((d / "qa.json").read_text()) if (d / "qa.json").exists() else {"status": "fail"}
                post = json.loads((d / "post.json").read_text())
                key = f"{post['campaign']}/{d.name}"
                index["clips"][key] = {"artifact_id": art["id"], "path": str(Path(n).parent), "campaign": post["campaign"],
                                       "score": post.get("score") or 0, "qa": qa["status"], "title": post["title"],
                                       "platforms": sorted(post["platforms"]), "created": art["created_at"][:10]}
        index["artifacts"][str(art["id"])] = art["name"]
        changed = True
    return changed


def pick(acc: dict, index: dict, posted: dict, camps: dict) -> str | None:
    p = acc["platform"]
    flt = acc.get("campaign_filter") or {}
    cutoff = (now().date() - dt.timedelta(days=12)).isoformat()
    best = None
    for key, c in index["clips"].items():
        camp = camps.get(c["campaign"])
        if (c["qa"] != "pass" or p not in c["platforms"] or c["created"] < cutoff or not camp
                or not camp.get("joined") or camp.get("status") != "open" or p not in (camp.get("platforms") or [])
                or f"{key}|{p}" in posted["clips"]
                or (flt.get("include") and c["campaign"] not in flt["include"]) or c["campaign"] in (flt.get("exclude") or [])):
            continue
        if cm.remaining_frac(camp) <= 0:
            continue
        if best is None or (c["score"], c["created"]) > (index["clips"][best]["score"], index["clips"][best]["created"]):
            best = key
    return best


def notify(rec: dict, camp: dict, post: dict) -> None:
    deadline = (dt.datetime.fromisoformat(rec["posted_at"]) + dt.timedelta(minutes=30)).strftime("%H:%M")
    if rec["platform"] == "tiktok" and not rec.get("url"):
        cap = post["platforms"]["tiktok"]["caption"]
        body = (f"**TikTok-Entwurf ist in deiner App.**\n\n1. TikTok öffnen → Benachrichtigung/Entwürfe → Video öffnen\n"
                f"2. Text einfügen (unten), bei Werbung „Markeninhalt“ einschalten, **Posten**\n"
                f"3. Sofort Link kopieren → [Kampagne]({camp['url']}) → Submit (**innerhalb 30 Min. nach dem Posten**)\n"
                f"4. Link als Kommentar hier + Issue schließen = eingereicht\n\n```\n{cap}\n```\n")
        title = f"TikTok posten + einreichen: {camp['title'][:60]}"
    else:
        body = (f"**Jetzt einreichen – spätestens {deadline} Uhr** (30 Min. nach dem Post)\n\n"
                f"Post: {rec['url']}\nKampagne: [{camp['title']}]({camp['url']})\n\n"
                f"1. Kampagnen-Link öffnen → **Submit** → Post-Link einfügen\n2. Dieses Issue schließen = eingereicht\n")
    body += f"\n<!--key:{rec['key']}|{rec['platform']}-->"
    if rec["platform"] != "tiktok" or rec.get("url"):
        title = f"Einreichen bis {deadline}: {camp['title'][:60]}"
    ghapi.create_issue(DATA, title, body, ["einreichen"])


def sync_submitted(posted: dict) -> bool:
    changed = False
    for iss in ghapi.issues(DATA, state="closed", label="einreichen"):
        m = re.search(r"<!--key:(.+?)\|(\w+)-->", iss.get("body") or "")
        if m:
            k = f"{m.group(1)}|{m.group(2)}"
            if k in posted["clips"] and not posted["clips"][k].get("submitted"):
                posted["clips"][k]["submitted"] = True
                posted["clips"][k]["submitted_at"] = iss.get("closed_at")
                changed = True
    return changed


def main() -> int:
    camps = {c["id"]: c for _, c in cm.load()}
    posted, psha = ghapi.get_json(DATA, "posted.json", {"clips": {}, "slots": {}})
    if sync_submitted(posted) and not DRY:
        psha = ghapi.put_json(DATA, "posted.json", posted, psha, "sync: eingereicht")
    slots = due_slots(posted)
    if not slots:
        print("Kein Slot fällig.")
        return 0
    index, isha = ghapi.get_json(DATA, "index.json", {"artifacts": {}, "clips": {}})
    if index_artifacts(index) and not DRY:
        isha = ghapi.put_json(DATA, "index.json", index, isha, "index: neue Clips")
    today = now().date().isoformat()
    for acc, slot in slots:
        key = pick(acc, index, posted, camps)
        if not key:
            print(f"{acc['id']} {slot}: kein passender Clip (beigetreten? QA pass? Plattform?)")
            continue
        c = index["clips"][key]
        print(f"{acc['id']} {slot}: Clip gewählt (Score {c['score']})")   # öffentliche Logs: keine Titel/Links
        if DRY:
            continue
        rec = {"key": key, "platform": acc["platform"], "account": acc["id"], "campaign": c["campaign"],
               "slot": slot, "status": "uploading", "posted_at": now().isoformat(timespec="seconds"), "submitted": False}
        posted["clips"][f"{key}|{acc['platform']}"] = rec          # Reservierung zuerst
        posted["slots"][f"{acc['id']}|{today}|{slot}"] = key
        psha = ghapi.put_json(DATA, "posted.json", posted, psha, f"reserve {acc['id']} {slot}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                art = {"archive_download_url": f"{ghapi.API}/repos/{ghapi.REPO}/actions/artifacts/{c['artifact_id']}/zip"}
                ghapi.download_artifact(art, tmp)
                d = Path(tmp) / c["path"]
                post = json.loads((d / "post.json").read_text())
                res = platforms.UPLOADERS[acc["platform"]](acc["secret_prefix"], d / "clip.mp4", post)
            new_rt = res.pop("new_refresh_token", None)
            if new_rt and new_rt != platforms.secret(f"{acc['secret_prefix']}_REFRESH_TOKEN"):
                ghapi.set_secret(f"{acc['secret_prefix']}_REFRESH_TOKEN", new_rt)   # TikTok rotiert Refresh-Tokens
            rec.update(status="draft" if res.get("mode") == "inbox" else "posted", url=res.get("url"),
                       platform_id=res.get("id"), posted_at=now().isoformat(timespec="seconds"))
        except Exception as e:  # noqa: BLE001
            rec.update(status="error", error=str(e)[:300])
            print("  FEHLER – Details im privaten Daten-Repo (Issue)")
            ghapi.create_issue(DATA, f"Fehler beim Posten ({acc['id']})", f"```\n{str(e)[:1500]}\n```\nClip: {key}", ["fehler"])
        posted["clips"][f"{key}|{acc['platform']}"] = rec
        psha = ghapi.put_json(DATA, "posted.json", posted, psha, f"{rec['status']} {acc['id']} {slot}")
        day, dsha = ghapi.get_json(DATA, f"days/{today}/posted.json", [])
        day.append(rec)
        ghapi.put_json(DATA, f"days/{today}/posted.json", day, dsha, f"log {acc['id']} {slot}")
        if rec["status"] in ("posted", "draft"):
            notify(rec, camps[c["campaign"]], post)
            print(f"  {rec['status']} – Einreich-Hinweis im privaten Daten-Repo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
