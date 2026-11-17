"""Zugangsdaten als GitHub-Secrets speichern (nie im Repo, nie im Chat).

Lokal ausführen (braucht `gh` CLI, angemeldet):
    python tools/auth.py set GEMINI_API_KEY          # fragt Wert verdeckt ab
    python tools/auth.py add-account youtube         # neuer Account-Eintrag + Secrets
    python tools/auth.py check                       # welche Secrets fehlen?

Plattform-OAuth (Tokens holen) folgt in Phase 4; dann speichert dieses Skript die Tokens.
"""
from __future__ import annotations

import getpass
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACCOUNTS = ROOT / "config" / "accounts.json"
REPO = "biceraras6-afk/stream-clips"

GLOBAL_SECRETS = ["GEMINI_API_KEY", "GROQ_API_KEY"]  # ANTHROPIC_API_KEY optional
# Secrets je Account (Präfix + Name). Werden in Phase 4 um OAuth-Tokens ergänzt.
PLATFORM_SECRETS = {
    "youtube": ["NAME", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"],
    "tiktok": ["NAME", "CLIENT_KEY", "CLIENT_SECRET", "REFRESH_TOKEN"],
    "instagram": ["NAME", "USER_ID", "ACCESS_TOKEN"],
    "x": ["NAME", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"],
}


def gh_set(name: str, value: str) -> None:
    subprocess.run(["gh", "secret", "set", name, "--repo", REPO], input=value.encode(), check=True)
    print(f"gespeichert: {name}")


def existing() -> set[str]:
    out = subprocess.run(["gh", "secret", "list", "--repo", REPO], capture_output=True, text=True, check=True)
    return {line.split()[0] for line in out.stdout.splitlines() if line.strip()}


def cmd_set(name: str) -> None:
    value = getpass.getpass(f"{name}: ")
    if not value:
        sys.exit("leer – abgebrochen")
    gh_set(name, value)


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
    print(f"Eintrag {acc['id']} angelegt (Platzhalter, keine echten Daten).")
    for s in PLATFORM_SECRETS[platform]:
        if s in ("NAME", "CLIENT_ID", "CLIENT_SECRET", "CLIENT_KEY", "USER_ID"):
            cmd_set(f"{acc['secret_prefix']}_{s}")
    print("Tokens (REFRESH_TOKEN/ACCESS_TOKEN) folgen per OAuth in Phase 4.")


def cmd_check() -> None:
    have = existing()
    need = list(GLOBAL_SECRETS)
    for a in json.loads(ACCOUNTS.read_text())["accounts"]:
        if a["active"]:
            need += [f"{a['secret_prefix']}_{s}" for s in PLATFORM_SECRETS[a["platform"]]]
    for n in need:
        print(("ok   " if n in have else "FEHLT") + " " + n)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    {"set": cmd_set, "add-account": cmd_add_account, "check": cmd_check}[cmd](*args)
