# stream-clips

Pipeline: Content-Rewards-Kampagnen finden → Stream-Clips bauen → auf YouTube/Instagram/TikTok posten → Einreich-Hinweis.
Läuft in GitHub Actions (öffentliches Repo). Details: `README.md`, `AUTOMATION.md`, `docs/SETUP.md`, `docs/RESEARCH.md`.

## Antwortstil
- Deutsch, nur Stichworte. Wenig Werkzeugaufrufe, kurze Ausgaben, keine Subagenten.
- Unsicherheiten offen benennen; prüfen statt raten.

## Regeln
- Qualität vor Menge, Hook zuerst: `docs/HOOKS.md`, Skill `stream-hooks`.
- Abo sparen: Dauerläufe nur als Skripte/Actions. Claude nur für Urteile (Sonnet), nie Opus im Dauerbetrieb. Massenarbeit über `tools/llm.py` (Gemini → Groq → Claude).
- Nie ins Repo: Zugangsdaten, Account-Namen/-IDs, gepostete Links, Protokolle, Statistiken. Secrets → GitHub-Secrets; Protokolle → privates Repo `stream-clips-data`. Öffentliche Logs ohne Titel/Links der Posts.
- Nur Quellen mit Freigabe der Kampagne (`source.permission_quote`). Keine Browser-Bots, kein Login-Bot für Content Rewards, keine Fake-Views, keine Massen-Accounts.
- CR-AGB: Einreichung ≤ 30 Min. nach Post; ein Post = eine Kampagne; Werbe-Hinweis am Videoanfang; politische Clips nie auf TikTok/X.
- Accounts nur in `config/accounts.json` (Platzhalter). Neuer Account = Eintrag + Workflow `auth`.

## Wichtige Dateien
- `tools/discover.py`, `tools/campaigns.py` – Kampagnen
- `tools/factory.py` (+ `candidates`, `hook`, `cut`, `postmeta`, `qa`) – Clips
- `tools/post.py`, `tools/platforms.py`, `tools/auth.py` – Posten/Verbinden
- `config/*.json` – Einstellungen
