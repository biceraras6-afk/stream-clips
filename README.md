# stream-clips

Pipeline: Stream-VODs → Kurzclips → Posten → Einreichen bei Content-Rewards-Kampagnen.

- `docs/RESEARCH.md` – Recherche, AGB, Risiken
- `campaigns/<id>.json` – Kampagnen (Vorlage `_example.json`)
- `config/` – Accounts (nur Platzhalter), Vorlieben, LLM-Anbieter
- `tools/llm.py` – LLM mit Fallback Gemini → Groq → Claude, Limits + Protokoll
- `tools/auth.py` – Zugangsdaten als GitHub-Secrets
- `tools/intake.py` – Kampagne aus Seitentext erfassen (Issue „Neue Kampagne“)
- `tools/campaigns.py` – prüfen, filtern, priorisieren, auto-stoppen
