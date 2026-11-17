"""Uploads über die offiziellen APIs: YouTube Data API, Instagram API (Instagram Login), TikTok Content Posting API.

Zugangsdaten je Account aus Secrets mit Präfix (z. B. YT1_*), übergeben als Umgebungsvariablen
oder als JSON in SECRETS_JSON (Workflow: toJSON(secrets)).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTING = json.loads((ROOT / "config" / "posting.json").read_text())
_SECRETS = json.loads(os.environ.get("SECRETS_JSON") or "{}")


class UploadError(Exception):
    pass


def secret(name: str) -> str | None:
    return os.environ.get(name) or _SECRETS.get(name)


def _http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, form: dict | None = None,
          timeout: int = 600) -> tuple[int, dict, bytes]:
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    r = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "stream-clips/0.1", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        raise UploadError(f"{method} {url.split('?')[0]}: HTTP {e.code} {e.read()[:400]!r}") from None


def _json(b: bytes) -> dict:
    return json.loads(b) if b else {}


# ---------- YouTube ----------

def youtube_token(prefix: str) -> str:
    _, _, b = _http("POST", "https://oauth2.googleapis.com/token", form={
        "client_id": secret(f"{prefix}_CLIENT_ID"), "client_secret": secret(f"{prefix}_CLIENT_SECRET"),
        "refresh_token": secret(f"{prefix}_REFRESH_TOKEN"), "grant_type": "refresh_token"})
    return _json(b)["access_token"]


def youtube_upload(prefix: str, mp4: Path, post: dict) -> dict:
    p = post["platforms"]["youtube"]
    tok = youtube_token(prefix)
    meta = {
        "snippet": {"title": p["title"][:100], "description": p["description"][:5000],
                    "tags": [h.lstrip("#") for h in post.get("hashtags", [])][:15],
                    "categoryId": POSTING["youtube_category_id"]},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False},
    }
    parts = "snippet,status"
    if post.get("disclosure"):
        meta["paidProductPlacementDetails"] = {"hasPaidProductPlacement": True}
        parts += ",paidProductPlacementDetails"
    size = mp4.stat().st_size
    _, h, _ = _http("POST", f"https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part={parts}",
                    data=json.dumps(meta).encode(), headers={
                        "Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    loc = h.get("Location") or h.get("location")
    _, _, b = _http("PUT", loc, data=mp4.read_bytes(), headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    v = _json(b)
    status = v.get("status", {})
    return {"id": v["id"], "url": f"https://www.youtube.com/shorts/{v['id']}", "privacy": status.get("privacyStatus"),
            "upload_status": status.get("uploadStatus")}


# ---------- Instagram (Reels, Instagram Login) ----------

IG = "https://graph.instagram.com"


def instagram_upload(prefix: str, mp4: Path, post: dict) -> dict:
    tok, uid = secret(f"{prefix}_ACCESS_TOKEN"), secret(f"{prefix}_USER_ID")
    cap = post["platforms"]["instagram"]["caption"]
    _, _, b = _http("POST", f"{IG}/{uid}/media", form={
        "media_type": "REELS", "upload_type": "resumable", "caption": cap, "share_to_feed": "true", "access_token": tok})
    c = _json(b)
    size = mp4.stat().st_size
    _http("POST", c["uri"], data=mp4.read_bytes(), headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)})
    for _ in range(60):                                  # bis zu 10 Min. Verarbeitung
        _, _, b = _http("GET", f"{IG}/{c['id']}?fields=status_code,status&access_token={tok}")
        st = _json(b)
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise UploadError(f"Instagram-Verarbeitung: {st}")
        time.sleep(10)
    else:
        raise UploadError("Instagram-Verarbeitung dauert zu lange")
    _, _, b = _http("POST", f"{IG}/{uid}/media_publish", form={"creation_id": c["id"], "access_token": tok})
    mid = _json(b)["id"]
    _, _, b = _http("GET", f"{IG}/{mid}?fields=permalink&access_token={tok}")
    return {"id": mid, "url": _json(b).get("permalink")}


def instagram_refresh(prefix: str) -> str:
    _, _, b = _http("GET", f"{IG}/refresh_access_token?grant_type=ig_refresh_token&access_token={secret(prefix + '_ACCESS_TOKEN')}")
    return _json(b)["access_token"]


# ---------- TikTok ----------

TT = "https://open.tiktokapis.com/v2"


def tiktok_token(prefix: str) -> tuple[str, str]:
    """-> (access_token, neuer refresh_token). Der neue Refresh-Token muss gespeichert werden."""
    _, _, b = _http("POST", f"{TT}/oauth/token/", form={
        "client_key": secret(f"{prefix}_CLIENT_KEY"), "client_secret": secret(f"{prefix}_CLIENT_SECRET"),
        "grant_type": "refresh_token", "refresh_token": secret(f"{prefix}_REFRESH_TOKEN")})
    j = _json(b)
    if "access_token" not in j:
        raise UploadError(f"TikTok-Token: {j}")
    return j["access_token"], j.get("refresh_token")


def tiktok_upload(prefix: str, mp4: Path, post: dict) -> dict:
    """Modus 'inbox': Video landet als Entwurf in der TikTok-App (du postest dort). Kein Audit nötig."""
    tok, new_refresh = tiktok_token(prefix)
    size = mp4.stat().st_size
    _, _, b = _http("POST", f"{TT}/post/publish/inbox/video/init/",
                    data=json.dumps({"source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size,
                                                     "total_chunk_count": 1}}).encode(),
                    headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"})
    j = _json(b)
    if (j.get("error") or {}).get("code") not in (None, "ok"):
        raise UploadError(f"TikTok init: {j['error']}")
    d = j["data"]
    _http("PUT", d["upload_url"], data=mp4.read_bytes(), headers={
        "Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}", "Content-Length": str(size)})
    return {"id": d["publish_id"], "url": None, "mode": "inbox", "new_refresh_token": new_refresh,
            "caption": post["platforms"]["tiktok"]["caption"]}


UPLOADERS = {"youtube": youtube_upload, "instagram": instagram_upload, "tiktok": tiktok_upload}
