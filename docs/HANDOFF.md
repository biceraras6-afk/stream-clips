# Übergabe für die nächste Sitzung (Stand 17.11.2026, 22:30)

Neue Sitzung: „Lies CLAUDE.md und docs/HANDOFF.md, mach beim nächsten Schritt weiter.“

## Fertig
- Phase 0–2b, 4, 5 gebaut. Kampagnensuche läuft alle 3 Std. (Groq + Gemini).
- Clip-Fabrik läuft (Kick + Twitch getestet, 6/6 QA pass) – Qualität laut Nutzer **schlecht**.
- Verbunden: Telegram (Test ok), GH_ADMIN_TOKEN (Test ok), Daten-Repo stream-clips-data, YouTube yt1 (Kanal gefunden).
- Nutzer ist noch KEINER Kampagne beigetreten → es wird nichts gepostet.

## Nächste Schritte (Reihenfolge)
1. **Bildschärfe** (Nutzer: „katastrophal unscharf“):
   - Quellauflösung in render.json loggen (ffprobe der section).
   - yt-dlp: beste Qualität erzwingen (`-S res,fps,br`), Kick-Formate prüfen.
   - Layout: bei 16:9 ohne Facecam kein starker Crop mehr → ganzes Bild skaliert in der Mitte + unscharfer Hintergrund oben/unten (oder Zoom max. 1,3×); Split nur mit echter Facecam.
   - Kodierung: crf 18, preset medium, 30/60 fps je Quelle.
2. **Untertitel** schöner: dickere Schrift (Montserrat/Anton via fonts im Repo), weniger Wörter pro Zeile, Position über TikTok-UI.
3. **Auswahl verbessern** (Momente laut Nutzer schlecht): Zuschauer-Clips (Twitch `/clips?filter=clips&range=7d`, Kick-Clips) als Hauptsignal (vod_offset → Fenster), Chat-Aktivität; Claude-Sonnet-Urteil erst nach Vergleich (Nutzer muss API-Kosten ~$5–12/Monat freigeben).
4. **Phase 3**: Top-Clips der Kampagne (campaign.references) analysieren → docs/STYLE.md.
5. Groq-429: Retry-After auswerten, Tokens/Minute drosseln (Post-Texte fielen auf Notlösung zurück).
6. Danach: Instagram (ig1) und TikTok (tt1) verbinden (docs/SETUP.md), erster echter Post nach Beitritt.

## Hinweise
- Workflows mit `toJSON(secrets)` werden von GitHub angehalten → Secrets einzeln übergeben (erledigt).
- Testläufe: Actions → clips → Kampagne `cr-74fcae70-cartier2real-stream-clips-1-1k-views` (Kick) oder `cr-16e8fdb7-5-000-ultimate-fighting-bots-campaign` (Twitch).
- Dashboard: https://claude.ai/artifact/548jwiLMNWHFdk8QYTjeyZ (Daten per tools/dashboard_data.py + Artifact-Upload).

## Ergänzung (17.11., spät) – Entscheidungen und offene Punkte
- **Nutzer ist bei Content Rewards noch keiner Kampagne beigetreten und hat im Issue „Beitreten“ NICHTS abgehakt.** Wichtig: Sobald er Cartier2Real abhakt, postet `post.yml` die vorhandenen schlechten Clips (Artefakte bis 12 Tage) öffentlich auf YouTube. → **Zuerst Posting-Schalter einbauen** (`config/posting.json` → `"enabled": false`, `tools/post.py` prüft ihn; Freigabe per Telegram „/go“ oder Datei-Flag), dann Bildqualität reparieren.
- Telegram-Push: Bot + Chat-ID gespeichert, Test ok. Instagram (ig1) und TikTok (tt1) noch nicht verbunden (docs/SETUP.md). Nutzer will vorerst nur **YouTube + Instagram**, TikTok später.
- **30-Min-Regel (CR AGB 7.12)** ist nicht änderbar. Offen: Zeiten, zu denen der Nutzer zuverlässig 5 Min. am Handy hat. Vorschlag: A) feste Slots nach Alltag, B) alle Plattformen in derselben Minute, E) zweite Erinnerung nach 15 Min. + „verpasst“-Meldung nach 30 Min., optional C) Posten auf Zuruf („/da“), D) „/pause“. Nutzer wollte das **später** klären, nachdem die Automatik steht.
- Offene Frage: Postet jeder Slot 3 Clips gleichzeitig? (Nutzer: später klären.)
- **Claude-API für Sonnet-Auswahl:** Nutzer überlegt Max-Abo (150 €). Hinweis gegeben: Betrieb braucht kein Abo; API (Haiku < $2/Monat, Sonnet ca. $4–30/Monat je nach Videos) wird separat abgerechnet. Entscheidung offen.
- Skalierung: Vorrat/Qualität, YouTube-Quota (Quellen widersprüchlich: ~6 vs ~100 Uploads/Tag/Projekt), Einreichen von Hand (≈ 20–30 pro Sitzung) begrenzen; erst ausbauen, wenn Phase 3 Mindest-Views zeigt. Ziel heute: 3 Clips/Tag.
- **Support-Anfrage an Content Rewards** (API/automatisches Einreichen, wie viele Social-Accounts verbindbar) vom Nutzer noch nicht gesendet/beantwortet; Antworttext liegt im Chatverlauf – bei Bedarf neu formulieren.
- Nutzerwunsch Antwortstil: kurz, Stichworte, deutsch. Sitzungen kurz halten (5-Std-Limit war bei 96 %).

## Stand 18.11. (nachts)
- **Erledigt + vom Nutzer bestätigt:** Bildschärfe (sehr gut), Fit-Layout mit Unschärfe-Hintergrund (gut), Untertitel ok. Posting-Schalter (`enabled: false`, Telegram /go /stop; Polling ungetestet).
- Erledigt, ungetestet: Groq-Retry-After, KI-Modelle je Modell gesperrt (Lauf #12: Anbieter ok), Pausenkürzung-Längenfix, True-Peak-Fix, `default_est_views` 1500, Zuschauer-Clips (Twitch, braucht TWITCH_CLIENT_ID/SECRET; Nutzer braucht dafür 2FA bei Twitch), Phase 3 `tools/style.py` (YouTube-API; Schlüssel als Secret vorhanden) – Zahlen: Länge Top ≈ 26 s, Titel ≈ 10 Wörter; STYLE.md noch nicht im Repo, KI-Regeln zu allgemein.
- Nutzerentscheidung: Menge vor Qualität; Selbstlauf mit Rückfrage-Grenzen (siehe CLAUDE.md).
- Offen: Kampagne zum Beitreten wählen (Kandidat: Ultimate Fighting Bots, Twitch; Lacy GTA VI Pool: Regeln/Quelle prüfen); Suche erweitern (Nutzer ja/nein); Support-Frage an CR (Frage 3: AGB 9.4, Frage 4: 30-Min-Frist); Claude-API (Kosten, Entscheidung offen); yt2, ig1, ig2 verbinden; Posting-Freigabe erst nach Beitritt.
- Laufzeit Fabrik: ~28 Min. für 4 Clips (Audio 5, Transkript 4, Bewertung 7 Min.).

## Erster echter Post (18.11., ca. 01:48 Uhr DE)
- Einmal-Post per `post.yml` mit `one_shot_account=yt1` (Cartier2Real, YouTube). Nutzer hat innerhalb der Frist eingereicht. Links/Protokoll nur im privaten Daten-Repo.
- Automatik bleibt gesperrt (`enabled: false`, Freigabe per Telegram `/go`). Fixes dabei: Artefakt-Download ohne Token auf Blob-Umleitung.
- Nächste Schritte: Views nach 24–48 Std. ansehen (Mindest-Views 5.000), danach entscheiden: Automatik freigeben, IG/TikTok verbinden (Nutzer: morgen), 30-Min-Slots festlegen.

## Antwort Content Rewards (18.11.)
- **Keine API und kein automatisches Einreichen.** Einreichen bleibt Handarbeit (<=30 Min. nach Post). Skalierung hängt am Zeitbudget des Nutzers (ca. 1–3 Min. je Post), nicht an der Technik.
- Hindernisse je Kampagne: Quelle (YouTube-Download von Actions gesperrt; Drive-Footage großer Dateien von Google gesperrt), Briefing nur eingeloggt/extern sichtbar (Sperre `briefing_checked`), Pflichtangaben je Kampagne (config/campaign_overrides.json).
- Gebaut diese Sitzung: Marken-Layout (Wasserzeichen), Einmal-Post (`one_shot_account`), Telegram-Meldung bei Fehlschlag, Kampagnen-Overrides (Loaded Tea Shop MJ, Tomo GTA VI, Cartier2Real).
