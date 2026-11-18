# Clips lokal am PC bauen (für Quellen, die GitHub-Server nicht laden dürfen, z. B. YouTube)

Läuft mit der Claude-Desktop-App (Code-Bereich) am eigenen PC/Mac, über die eigene Internetverbindung.
Es gibt keine Secrets im Repo: KI-Schlüssel (Gemini/Groq, kostenlos) setzt du lokal als Umgebungsvariablen.

## Einmalig
1. Claude-Desktop-App installieren, mit dem Konto anmelden.
2. Code-Bereich -> neuen Ordner wählen (z. B. `clips`) und diesen Auftrag eingeben:

> Klone https://github.com/biceraras6-afk/stream-clips in diesen Ordner. Installiere git, Python 3.12+, ffmpeg und die Pakete aus requirements.txt. Lies CLAUDE.md. Setze die Umgebungsvariablen GROQ_API_KEY und GEMINI_API_KEY (ich gebe sie dir getrennt, nicht ins Repo schreiben). Dann baue Clips: `python tools/factory.py --campaign <Kampagnen-ID> --url <Video-Link> --max-clips 3`. Zeig mir die fertigen Clips (out/clips/…/clip.mp4 und post.json).

## Danach
- Fertige Clips liegen in `out/clips/<kampagne>/…/clip.mp4`, Titel/Beschreibung/Tags in `post.json` (inkl. Pflichtangaben der Kampagne, CTA ist im Video).
- Posten: von Hand auf YouTube/Instagram/TikTok (die Automatik kennt lokale Clips nicht). Einreichen <= 30 Min.
- Tomo GTA VI: Kampagnen-ID `cr-df6de26f-tomo-gta-vi-clipping`.
- Nie ins Repo: Schlüssel, Links gepostete Clips, Statistiken.
