"""GitHub-API-Helfer: Secrets setzen, privates Daten-Repo lesen/schreiben, Issues, Artefakte.

Token: GH_ADMIN_TOKEN (fein granular, nur dieses Repo + Daten-Repo) oder GITHUB_TOKEN für Lesezugriffe.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request
import zipfile

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "biceraras6-afk/stream-clips")


def _token(admin: bool = False) -> str:
    t = os.environ.get("GH_ADMIN_TOKEN") if admin else (os.environ.get("GH_ADMIN_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    if not t:
        raise RuntimeError("GH_ADMIN_TOKEN fehlt (Secret anlegen, siehe docs/SETUP.md)")
    return t


def req(method: str, path: str, body=None, admin: bool = False, raw: bool = False, accept: str = "application/vnd.github+json"):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_token(admin)}", "Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stream-clips", **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            out = resp.read()
            return out if raw else (json.loads(out) if out else {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"GitHub {method} {path}: {e.code} {e.read()[:300]!r}") from None


# ---------- Secrets ----------

def set_secret(name: str, value: str, repo: str = REPO) -> None:
    from nacl import encoding, public
    key = req("GET", f"/repos/{repo}/actions/secrets/public-key", admin=True)
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    req("PUT", f"/repos/{repo}/actions/secrets/{name}", {"encrypted_value": enc, "key_id": key["key_id"]}, admin=True)
    print(f"Secret gespeichert: {name}")


# ---------- Daten-Repo (privat) ----------

def get_json(repo: str, path: str, default=None):
    r = req("GET", f"/repos/{repo}/contents/{path}", admin=True)
    if not r:
        return default, None
    return json.loads(base64.b64decode(r["content"])), r["sha"]


def put_json(repo: str, path: str, data, sha: str | None, message: str) -> str:
    body = {"message": message, "content": base64.b64encode(json.dumps(data, indent=1, ensure_ascii=False).encode()).decode()}
    if sha:
        body["sha"] = sha
    return req("PUT", f"/repos/{repo}/contents/{path}", body, admin=True)["content"]["sha"]


def create_issue(repo: str, title: str, body: str, labels: list[str] | None = None) -> dict:
    return req("POST", f"/repos/{repo}/issues", {"title": title, "body": body, "labels": labels or []}, admin=True)


def issues(repo: str, state: str = "all", label: str | None = None) -> list[dict]:
    q = f"?state={state}&per_page=100" + (f"&labels={label}" if label else "")
    return req("GET", f"/repos/{repo}/issues{q}", admin=True) or []


# ---------- Artefakte der Clip-Läufe ----------

def clip_artifacts(repo: str = REPO) -> list[dict]:
    r = req("GET", f"/repos/{repo}/actions/artifacts?per_page=100") or {}
    return [a for a in r.get("artifacts", []) if a["name"].startswith("clips-") and not a["expired"]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _download(url: str) -> bytes:
    """Artefakt laden: GitHub leitet auf Blob-Speicher um – dorthin darf der Token NICHT mit (sonst 401)."""
    r = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}", "Accept": "application/vnd.github+json",
                                             "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "stream-clips"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(r, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        if e.code in (301, 302, 303, 307, 308) and loc:
            with urllib.request.urlopen(urllib.request.Request(loc, headers={"User-Agent": "stream-clips"}), timeout=600) as resp:
                return resp.read()
        raise RuntimeError(f"GitHub GET {url}: {e.code}") from None


def download_artifact(a: dict, dest) -> list[str]:
    data = _download(a["archive_download_url"])
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
        return z.namelist()
