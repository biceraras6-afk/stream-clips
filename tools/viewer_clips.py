"""Zuschauer-Clips als Auswahl-Signal: Was Zuschauer selbst geclippt haben, ist ein starker Hinweis auf gute Momente.

Twitch (offizielle Helix-API, Secrets TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET): Clips eines VODs mit vod_offset.
Kick: keine offizielle, stabile Clip-API ohne Login -> hier bewusst nicht gebaut (keine Browser-Bots).
Ohne Secrets: leere Liste, Fabrik läuft wie bisher.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _get(url: str, headers: dict, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "stream-clips/0.1", **headers})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def twitch_clips(meta: dict) -> list[dict]:
    """[{s, e, views}] in Sekunden des VODs; leer bei fehlenden Secrets/Fehlern."""
    cid, sec = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
    vid = str(meta.get("id") or "").lstrip("v")
    login = meta.get("uploader_id") or meta.get("channel_id")
    if not (cid and sec and vid.isdigit() and login):
        return []
    try:
        tok = _get("https://id.twitch.tv/oauth2/token", {}, urllib.parse.urlencode(
            {"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}).encode())["access_token"]
        h = {"Client-Id": cid, "Authorization": f"Bearer {tok}"}
        users = _get("https://api.twitch.tv/helix/users?login=" + urllib.parse.quote(str(login)), h)["data"]
        if not users:
            return []
        out, cursor = [], ""
        for _ in range(5):
            q = f"https://api.twitch.tv/helix/clips?broadcaster_id={users[0]['id']}&first=100" + (f"&after={cursor}" if cursor else "")
            r = _get(q, h)
            out += [c for c in r["data"] if str(c.get("video_id")) == vid and c.get("vod_offset") is not None]
            cursor = (r.get("pagination") or {}).get("cursor", "")
            if not cursor:
                break
    except Exception:  # noqa: BLE001
        return []
    return [{"s": float(c["vod_offset"]), "e": float(c["vod_offset"]) + float(c.get("duration") or 30),
             "views": int(c.get("view_count") or 0)} for c in out]
