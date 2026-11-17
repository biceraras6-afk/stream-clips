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
