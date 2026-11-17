# Automatischer Betrieb

## Zeitplan (Europe/Berlin)
| Wann | Workflow | Was | Claude-Abo |
|---|---|---|---|
| alle 3 Std. | `campaigns` | Kampagnen finden, Budgets aktualisieren, Auto-Stopp, Issue „Beitreten“ | – |
| täglich 06:17 | `daily` → `clips` | Clips für die besten beigetretenen Kampagnen bauen (Hook, QA) | – |
| alle 30 Min. | `post` | fällige Slots posten (YouTube, Instagram, TikTok-Entwurf), Einreich-Hinweis | – |
| montags | `tokens` | Instagram-Token erneuern | – |
| bei Bedarf | `auth` | Account verbinden | – |

Posting-Slots: `config/posting.json` (Standard 14:00, 18:00, 22:00 – je Plattform 10 Min. versetzt).
Gratis-LLMs: Gemini → Groq; Claude nur mit `ANTHROPIC_API_KEY` oder in einer geplanten Sonnet-Sitzung (optional).

## Was du täglich per Hand tust
1. Push „Einreichen bis HH:MM“ → Kampagnen-Link → **Submit** → Issue schließen (≤ 30 Min. nach Post, CR-Regel).
2. TikTok (bis Audit): Entwurf in der App posten, dann einreichen.
3. Neue Kampagnen im Issue „Beitreten“: beitreten + abhaken.

## Pausieren
- Alles: Actions → Workflow → „…“ → **Disable workflow** (`post` zuerst, dann `daily`, `campaigns`).
- Eine Plattform/einen Account: in `config/accounts.json` `"active": false`.
- Eine Kampagne: in `campaigns/<id>.json` `"status": "stopped"` (wird bei leerem Budget automatisch gesetzt).

## Kosten
- GitHub Actions: öffentliches Repo → Minuten kostenlos. Grobe Laufzeit/Tag: campaigns 8 × 3–12 Min., daily 1–3 Kampagnen × 20–90 Min. (Transkript langer VODs), post 48 × < 1 Min.
- LLM: Gemini/Groq Gratis-Kontingent; Verbrauch je Lauf in `state/llm_usage.jsonl` (Actions-Cache).
- Claude-Abo: im Dauerbetrieb **0** (keine Claude-Sitzung nötig). Optional: tägliche Sonnet-Sitzung für Hook-Urteile.
- Speicher: Clips als Lauf-Artefakte (14 Tage), Protokolle im privaten Repo `stream-clips-data`.

## Grenzen beim Skalieren (pro Plattform)
| Accounts | Clips/Tag (3 je Account) | GitHub-Minuten | Plattform-Limits | Handarbeit | Risiko |
|---|---|---|---|---|---|
| 1 | 3 | ok | ok | 9 Einreichungen/Tag (3 Plattformen) | gering |
| 3 | 9 | ok (mehr Quellen/Tag, parallel 3) | YouTube: Upload-Kontingent ~100/Tag pro Projekt ok; IG 50/Tag ok | 27 Einreichungen/Tag – Slots staffeln | CR bewertet verbundene Accounts gemeinsam (AGB 9.4) |
| 5 | 15 | Fabrik-Laufzeit steigt; ggf. max-parallel erhöhen | TikTok Entwürfe: jedes Video in der App posten | 45 Einreichungen – kaum per Hand machbar | Gleicher Clip nie doppelt pro Plattform (eingebaut) |
| 10 | 30 | 6-Std.-Grenze pro Job beachten | YouTube-Kontingent prüfen (ein Projekt je ~10 Accounts) | nicht ohne CR-API machbar | Spam-Erkennung der Plattformen, eigene Inhalte je Account nötig |

Ausbau erst, wenn Phase 3 zeigt, dass die Clips im Schnitt die Mindest-Views erreichen.
