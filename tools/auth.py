"""Zugänge verbinden und als GitHub-Secrets speichern (nie im Repo, nie im Chat).

Ohne PC, nur Browser (empfohlen) – Workflow „auth“ in GitHub Actions:
  1. Run workflow: account=yt1, schritt=link   -> Anmelde-Link steht in der Zusammenfassung des Laufs
  2. Link öffnen, anmelden, „Erlauben“. Die Seite danach zeigt eine Adresse mit ?code=...
  3. Run workflow: account=yt1, schritt=code, code=<ganze Adresse oder nur der Code>
     -> Tokens werden direkt als Secrets gespeichert.

Lokal (mit gh CLI):
  python tools/auth.py set NAME                 # Wert verdeckt eingeben
  python tools/auth.py add-account instagram    # neuer Account-Eintrag (Platzhalter)
  python tools/auth.py check                    # fehlende Secrets anzeigen
"""
from __future__ import annotations

import getpass
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ACCOUNTS = ROOT / "config" / "accounts.json"
POSTING = json.loads((ROOT / "config" / "posting.json").read_text())
REPO = "biceraras6-afk/stream-clips"

GLOBAL_SECRETS = ["GEMINI_API_KEY", "GROQ_API_KEY", "GH_ADMIN_TOKEN"]
# Von dir einzutragen (aus der Entwickler-Konsole der Plattform) | per Anmeldung automatisch gespeichert
PLATFORM_SECRETS = {
    "youtube": (["CLIENT_ID", "CLIENT_SECRET"], ["REFRESH_TOKEN"]),
    "instagram": (["APP_ID", "APP_SECRET"], ["ACCESS_TOKEN", "USER_ID"]),
    "tiktok": (["CLIENT_KEY", "CLIENT_SECRET"], ["REFRESH_TOKEN", "OPEN_ID"]),
    "x": (["CLIENT_ID", "CLIENT_SECRET"], ["REFRESH_TOKEN"]),
}


def account(aid: str) -> dict:
    for a in json.loads(ACCOUNTS.read_text())["accounts"]:
        if a["id"] == aid:
            return a
    sys.exit(f"Account {aid} nicht in config/accounts.json")


def store(name: str, value: str) -> None:
    if os.environ.get("GH_ADMIN_TOKEN"):
        from tools import ghapi
        ghapi.set_secret(name, value)
    else:
        subprocess.run(["gh", "secret", "set", name, "--repo", REPO], input=value.encode(), check=True)
        print(f"gespeichert: {name}")


def _s(name: str) -> str:
    from tools.platforms import secret
    v = secret(name)
    if not v:
        sys.exit(f"Secret {name} fehlt – erst in GitHub eintragen (siehe docs/SETUP.md)")
    return v


def link(aid: str) -> str:
    a = account(aid)
    p, pre = a["platform"], a["secret_prefix"]
    ru = POSTING["redirect_uri"][p]
    if p == "youtube":
        q = {"client_id": _s(f"{pre}_CLIENT_ID"), "redirect_uri": ru, "response_type": "code",
             "scope": POSTING["scopes"]["youtube"], "access_type": "offline", "prompt": "consent"}
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)
    if p == "instagram":
        q = {"client_id": _s(f"{pre}_APP_ID"), "redirect_uri": ru, "response_type": "code",
             "scope": POSTING["scopes"]["instagram"]}
        return "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode(q)
    if p == "tiktok":
        q = {"client_key": _s(f"{pre}_CLIENT_KEY"), "redirect_uri": ru, "response_type": "code",
             "scope": POSTING["scopes"]["tiktok"], "state": aid}
        return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)
    sys.exit(f"Plattform {p} noch nicht unterstützt")


def exchange(aid: str, code_or_url: str) -> None:
    from tools.platforms import _http, _json
    a = account(aid)
    p, pre = a["platform"], a["secret_prefix"]
    code = code_or_url.strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query)["code"][0]
    code = code.split("#")[0]
    print(f"::add-mask::{code}")
    ru = POSTING["redirect_uri"][p]
    if p == "youtube":
        _, _, b = _http("POST", "https://oauth2.googleapis.com/token", form={
            "client_id": _s(f"{pre}_CLIENT_ID"), "client_secret": _s(f"{pre}_CLIENT_SECRET"), "code": code,
            "redirect_uri": ru, "grant_type": "authorization_code"})
        j = _json(b)
        if "refresh_token" not in j:
            sys.exit("Kein Refresh-Token erhalten – Link neu erzeugen (prompt=consent) und erneut anmelden.")
        store(f"{pre}_REFRESH_TOKEN", j["refresh_token"])
        # Kanal prüfen
        _, _, b = _http("GET", "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                        headers={"Authorization": f"Bearer {j['access_token']}"})
        items = _json(b).get("items") or []
        print(f"Verbunden: YouTube-Kanal {'gefunden' if items else 'NICHT gefunden'} (Name bleibt aus Datenschutzgründen ungeloggt)")
    elif p == "instagram":
        _, _, b = _http("POST", "https://api.instagram.com/oauth/access_token", form={
            "client_id": _s(f"{pre}_APP_ID"), "client_secret": _s(f"{pre}_APP_SECRET"),
            "grant_type": "authorization_code", "redirect_uri": ru, "code": code})
        short = _json(b)
        _, _, b = _http("GET", "https://graph.instagram.com/access_token?" + urllib.parse.urlencode({
            "grant_type": "ig_exchange_token", "client_secret": _s(f"{pre}_APP_SECRET"), "access_token": short["access_token"]}))
        long = _json(b)
        print(f"::add-mask::{long['access_token']}")
        store(f"{pre}_ACCESS_TOKEN", long["access_token"])
        store(f"{pre}_USER_ID", str(short.get("user_id")))
        print(f"Verbunden: Instagram, Token gültig {int(long.get('expires_in', 0)) // 86400} Tage (wird wöchentlich erneuert)")
    elif p == "tiktok":
        _, _, b = _http("POST", "https://open.tiktokapis.com/v2/oauth/token/", form={
            "client_key": _s(f"{pre}_CLIENT_KEY"), "client_secret": _s(f"{pre}_CLIENT_SECRET"), "code": code,
            "grant_type": "authorization_code", "redirect_uri": ru})
        j = _json(b)
        if "refresh_token" not in j:
            sys.exit(f"TikTok-Anmeldung fehlgeschlagen: {j.get('error')} {j.get('error_description')}")
        store(f"{pre}_REFRESH_TOKEN", j["refresh_token"])
        store(f"{pre}_OPEN_ID", j.get("open_id", ""))
        print(f"Verbunden: TikTok, Rechte: {j.get('scope')}")


def cmd_set(name: str) -> None:
    value = getpass.getpass(f"{name}: ")
    if not value:
        sys.exit("leer – abgebrochen")
    store(name, value)


def cmd_add_account(platform: str) -> None:
    if platform not in PLATFORM_SECRETS:
        sys.exit(f"Plattform unbekannt: {platform}")
    data = json.loads(ACCOUNTS.read_text())
    n = 1 + sum(a["platform"] == platform for a in data["accounts"])
    short = {"youtube": "yt", "tiktok": "tt", "instagram": "ig", "x": "x"}[platform]
    acc = {"id": f"{short}{n}", "platform": platform, "secret_prefix": f"{short.upper()}{n}",
           "active": True, "campaign_filter": {"include": [], "exclude": []}}
    data["accounts"].append(acc)
    ACCOUNTS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Eintrag {acc['id']} angelegt. Jetzt Secrets {', '.join(acc['secret_prefix'] + '_' + s for s in PLATFORM_SECRETS[platform][0])} "
          f"eintragen und Workflow „auth“ ausführen.")


def cmd_check() -> None:
    from tools.platforms import secret
    need = list(GLOBAL_SECRETS)
    for a in json.loads(ACCOUNTS.read_text())["accounts"]:
        if a["active"]:
            manual, auto = PLATFORM_SECRETS[a["platform"]]
            need += [f"{a['secret_prefix']}_{s}" for s in manual + auto]
    for n in need:
        print(("ok   " if secret(n) else "FEHLT") + " " + n)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "link":
        url = link(args[0])
        print(url)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(f"### Anmelde-Link für {args[0]}\n\n[Hier anmelden]({url})\n\nDanach die Adresse der Folgeseite "
                        f"(enthält `code=`) kopieren und Workflow „auth“ mit schritt=code erneut starten. Der Code gilt nur wenige Minuten.\n")
    elif cmd == "code":
        exchange(args[0], args[1] if len(args) > 1 else os.environ.get("AUTH_CODE", ""))
    else:
        {"set": cmd_set, "add-account": cmd_add_account, "check": cmd_check}[cmd](*args)
