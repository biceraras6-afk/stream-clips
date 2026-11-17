# HOOKS – Regeln für die ersten 1–3 Sekunden

Gilt für jede Clip-Auswahl (Gratis-LLM, Claude-Urteil, `tools/hook.py`). Kurz halten: wird als Prompt mitgeschickt.

## Regeln
1. **Kaltstart.** Nie mit Anlauf, Begrüßung, „so anyway“, Ladebildschirm oder Stille beginnen. Start mitten in der Aktion oder Sekunden vor dem Höhepunkt.
2. **Erstes Bild = stärkstes Bild.** Gesicht mit Reaktion oder sichtbare Action. Kein Menü, kein Standbild.
3. **Erstes Wort sofort** (< 0,4 s). Kein abgeschnittenes Wort, kein Satz-Fragment.
4. **Erster Satz macht allein neugierig:** Frage, Behauptung, Konflikt, Zahl/Rekord, Kontrast. Fehlt er → **Flash-Forward**: 0,5–1,5 s des Höhepunkts vorn, dann zurück zum Anfang.
5. **Hook-Text (Overlay, 0–2 s):** max. 6–8 Wörter, groß, oben im sicheren Bereich. Öffnet eine Frage, die erst am Ende aufgelöst wird. **Keine Lüge** – der Clip muss halten, was der Text verspricht. Kampagnenregeln zu Overlays haben Vorrang.
6. **Werbe-Hinweis** (`#ad` o. Ä.) am Videoanfang, wenn die Kampagne ihn verlangt (CR-AGB 12.9). Er darf den Hook-Text nicht verdecken.
7. **Pointe am Ende,** danach sofort Schluss. Wo möglich führt das Ende sauber zurück in den Anfang (Loop).
8. **Nie** Streamer oder Marke schlecht machen, keine erfundenen Ergebnisse oder Dramen (häufige Kampagnenregel).

## Hook-Typen
| Typ | Erkennungszeichen | Overlay-Muster |
|---|---|---|
| Reaktion | Schrei, Lachen, Fassungslosigkeit in Sekunde 0 | „He did NOT expect this“ |
| Konflikt | Streit, Widerspruch, „No, you…“ | „This got heated fast“ |
| Wait for it | ruhiger Aufbau, klarer Knall am Ende → Teaser vorn | „Wait for the end…“ |
| Frage | Frage im ersten Satz | Frage wiederholen/zuspitzen |
| Zahl/Rekord | Zahl, Geld, Rekord, Wette | „$10,000 on one round“ |
| Kontrast | Erwartung vs. Ergebnis | „Easiest win… or not“ |
| Insider/Drama | Enthüllung, Geheimnis, Gerücht (nur wenn belegt) | „He finally said it“ |

## Messen (je Clip, automatisch in post.json → `hook`)
Typ · Sekunden bis zur ersten Pointe · erstes Wort · Lautstärke Sek. 0–2 relativ zum Median · Bewegung · Gesicht im Bild · Lücke bis zum ersten Wort · Fragment ja/nein · Loop-Wert.

## Beispiele aus Top-Clips
Wird in Phase 3 aus den Referenz-Clips der Kampagnen gefüllt (je Typ 5 echte Beispiele: Link, erstes Wort, Bild in Sek. 0, Zeit bis zur Pointe).

## Ergebnisse eigener Clips
Wird in Phase 3 aus der Feedback-Schleife gefüllt. Hooks mit Hold-Rate (3 s) unter dem eigenen Schnitt → **schwach**; gewinnende Muster → **bevorzugt**.

| Muster | Clips | Ø Hold-Rate 3 s | Ø Wiedergabe % | Status |
|---|---|---|---|---|
| – | – | – | – | – |
