"""Beitritts-Liste als GitHub-Issue mit Häkchen (Beitreten braucht Login -> per Hand).

    python tools/joinlist.py sync      # abgehakte Kampagnen im Issue -> joined=true
    python tools/joinlist.py publish   # Issue „Beitreten“ aus out/join.json neu schreiben

Du: Link öffnen -> „Join Campaign“ -> im Issue abhaken. Fertig.
Braucht `gh` (in Actions mit GH_TOKEN).
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LABEL = "join-list"
TITLE = "Beitreten: neue Kampagnen"


def gh(*args: str, input: str | None = None) -> str:
    return subprocess.run(["gh", *args], input=input, capture_output=True, text=True, check=True).stdout


def find_issue() -> tuple[int, str] | None:
    out = json.loads(gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number,body", "--limit", "1"))
    return (out[0]["number"], out[0]["body"]) if out else None


def checked_ids(body: str) -> set[str]:
    return set(re.findall(r"^- \[[xX]\] .*?<!--id:([\w.-]+)-->", body, re.M))


def sync(body: str | None = None) -> int:
    if body is None:
        found = find_issue()
        if not found:
            return 0
        body = found[1]
    n = 0
    for cid in checked_ids(body):
        p = ROOT / "campaigns" / f"{cid}.json"
        if p.exists():
            c = json.loads(p.read_text())
            if not c.get("joined"):
                c["joined"] = True
                p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
                n += 1
                print(f"beigetreten: {cid}")
    return n


def render(items: list[dict]) -> str:
    lines = ["Link öffnen → **Join Campaign** → hier abhaken. Die Pipeline übernimmt ab dann.", "",
             "Sortiert nach erwartetem Ertrag pro Clip. Wird automatisch aktualisiert.", ""]
    for i in items:
        extra = " · ⚠️ Bewerbung nötig" if i["application"] else ""
        rate = f"${i['rate']}/1K" if i.get("rate") else i.get("model", "")
        lines.append(f"- [ ] **{i['score']}** [{i['title']}]({i['url']}) · {rate} · Rest {i['remaining']:.0%} · "
                     f"{', '.join(i['platforms'])}{extra} <!--id:{i['id']}-->")
    if not items:
        lines.append("_Gerade keine passenden neuen Kampagnen._")
    return "\n".join(lines) + "\n"


def publish() -> None:
    items = json.loads((ROOT / "out" / "join.json").read_text())
    body = render(items)
    found = find_issue()
    if found:
        gh("issue", "edit", str(found[0]), "--body-file", "-", input=body)
    else:
        subprocess.run(["gh", "label", "create", LABEL, "--force", "--color", "0e8a16"], capture_output=True)
        gh("issue", "create", "--title", TITLE, "--label", LABEL, "--body-file", "-", input=body)
    print(f"Issue aktualisiert: {len(items)} Kampagnen")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "sync":
        import os
        sync(os.environ.get("ISSUE_BODY"))
    elif cmd == "publish":
        publish()
    else:
        sys.exit(__doc__)
