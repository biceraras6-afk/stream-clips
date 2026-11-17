# Phase 0 – Recherche (Stand 2026-11-17)

Legende: ✅ belegt (offizielle Quelle) · ⚠️ nur Drittquellen / widersprüchlich · ❓ offen, vor Umsetzung prüfen

## 1. Content Rewards (CR)

| Thema | Ergebnis | Status |
|---|---|---|
| Ablauf | Brand finanziert Kampagne → Clipper postet auf **eigenen** Accounts → reicht Post-Link ein → Brand prüft manuell → Bezahlung nach Views bis Budget leer | ✅ |
| Bezahlmodelle | CPM (pro 1.000 Views, Cap pro Clip), Fixbetrag pro Post, Retainer; manche aus gemeinsamem Pool | ✅ |
| Raten | meist $0,50–2 / 1.000 Views | ⚠️ |
| Mindestanforderungen | Mindest-Views (Payout-Schwelle) je Kampagne; darunter keine Prüfung | ✅ |
| Zählfenster | Clips ab 25.09.2026: 30 Tage ab Erreichen der Schwelle | ✅ |
| Gebühr / Auszahlung | 10 % auf CPM-Verdienst; Auszahlung über Whop | ✅ |
| View-Zählung | CR liest Views zeitversetzt von der Plattform | ✅ |
| Ablehnungsgründe | falsche Plattform, fehlende Tags/Disclosure, wiederverwendeter Inhalt, Post nach Einreichung bearbeitet/gelöscht | ✅ |
| Botting | gekaufte/erzeugte Views, Likes, Follower → **permanenter Bann** | ✅ |
| API | **keine offizielle Kampagnen-API gefunden.** Whop-API hat Beta-Endpunkte „bounties“ (`/api/v1/bounties/{id}/submissions`, öffentl. Einreichungen) – ob CR-Kampagnen darüber laufen, unklar | ❓ |
| Export / Kampagnenliste | öffentliche Kampagnenseite; nur Drittanbieter-Scraper (Apify) – nicht offiziell, nicht nutzen | ⚠️ |
| AGB zu Automatisierung | Creator-ToS verbieten klar Botting; Aussage zu Scraping/Bots für Einreichung **nicht gefunden** | ❓ |

**Folgerung:** Kampagnen-Erfassung & Einreichung vorerst **halbautomatisch**. Vor Phase 1: CR-ToS vollständig lesen (Scraping/Automatisierung), Whop-API-Doku auf Kampagnen-/Einreichungs-Endpunkt prüfen, ggf. CR-Support fragen.

## 2. Plattformen

| Plattform | Offizielle Upload-API | Prüfung/Audit | Limits | Inhalt-Regeln / Risiko |
|---|---|---|---|---|
| **TikTok** | Content Posting API (Direct Post; Upload in Entwürfe) | ✅ Audit nötig: ungeprüft nur **privat**, max. 5 Nutzer/24 h | Posts/Tag pro Creator begrenzt (⚠️ ~15), über alle Apps geteilt; Fehler `spam_risk_too_many_posts` | Unoriginal-Regel nicht recherchiert ❓; Audit-Dauer Tage–Wochen ⚠️ |
| **YouTube Shorts** | Data API `videos.insert` | ⚠️ ungeprüfte Projekte (nach 07/2020) laut Revision-History nur privat; aktuelle Upload-Doku widerspricht → live prüfen | 10.000 Einheiten/Tag; Upload-Kosten laut Drittquellen inzwischen ~100 statt 1.600 ⚠️ | Reused-Content-Policy (betrifft YPP-Monetarisierung, nicht CR-Bezahlung) ✅; Reichweiten-Abwertung für Re-Uploads seit 10/2026 ⚠️ → eigener Mehrwert (Schnitt, Untertitel, Hook) nötig |
| **Instagram Reels** | Graph API Content Publishing | App-Review + Business/Creator-Account | 50 (oder 100, Doku widersprüchlich) Posts/24 h; live über `content_publishing_limit` | Container verfallen nach 24 h |
| **X** | API v2 + Media Upload | Developer-Account | kein Gratis-Tier mehr; Pay-per-use ⚠️ ~$0,015/Post | Kosten pro Post → nur bei Kampagnenbedarf |

## 3. Stream-Quellen

| Quelle | Lage | Status |
|---|---|---|
| Twitch | ToS verbieten Download außer ausdrücklich erlaubt | ⚠️ (Zitat aus Sekundärquelle) |
| Kick | ToS verbieten Scraping/Bots; fremde VODs nur mit Erlaubnis | ⚠️ |
| YouTube-VODs | Download per YouTube-ToS nur über offizielle Wege | ❓ |
| Kampagnen-Material | viele Kampagnen geben eigene Quellen (Drive-Ordner, Kanal) frei | ❓ je Kampagne |

**Regel:** `yt-dlp` nur für Quellen, die die Kampagne ausdrücklich freigibt; Freigabe-Zitat in `campaigns/<id>.json` speichern. Ohne Freigabe kein Download.

## 4. LLM-Gratis-Kontingente
Gemini (AI Studio) und Groq: Limits/Nutzungsbedingungen noch nicht recherchiert ❓ → in Phase 1 vor `tools/llm.py` prüfen (u. a. ob Gratis-Daten für Training genutzt werden).

## 5. Hauptrisiken
1. Kein offizieller CR-Kampagnen-/Einreichungszugang → Automatisierung von Phase 1/4 begrenzt.
2. TikTok-Audit: bis bestanden nur private Posts → für CR wertlos (Views zählen nicht).
3. YouTube: Privat-Sperre ungeprüfter Projekte unklar; Audit evtl. nötig.
4. Quellenrechte: Download nur mit Kampagnen-Freigabe.
5. Reichweiten-Abwertung unoriginaler Clips (YT 10/2026) → Mehrwert pro Clip Pflicht.
6. Bann-Risiko bei allem, was nach Botting aussieht (Massen-Posting, viele Accounts, gleicher Clip mehrfach).

## 6. Vorschlag: Automatisierungsgrad

| Schritt | Grad | Begründung |
|---|---|---|
| Quelle holen, Transkript, Kandidaten, Schnitt, QA, `post.json` | **voll automatisch** (GitHub Actions) | eigene Rechenarbeit, keine Fremd-AGB betroffen (Quelle freigegeben) |
| Hook-/Clip-Auswahl | voll automatisch (Gemini/Groq vorsortieren, Sonnet final) | – |
| YouTube-Upload | **voll automatisch**, sobald öffentlich möglich (sonst Audit beantragen) | offizielle API |
| TikTok-Upload | **halbautomatisch** bis Audit: Upload in Entwürfe/Inbox per API, ich veröffentliche in der App; danach Direct Post | ungeprüft nur privat |
| Instagram/X | später, nur wenn Kampagne es verlangt | App-Review bzw. Kosten |
| Kampagnen finden | **halbautomatisch**: ich öffne Kampagnenseite, Skript nimmt Kampagnendaten (Copy/Paste oder gespeicherte Seite) auf und füllt `campaigns/<id>.json`; voll automatisch nur, wenn offizielle API/Erlaubnis bestätigt | ToS-Lage offen |
| Kampagne beitreten | **per Hand** (Liste mit Link) | – |
| Einreichen | **halbautomatisch**: Liste „bereit zum Einreichen“ mit Post-Link + Kampagnen-Link | keine API bestätigt |
| Statistik | YouTube Analytics API automatisch; TikTok über Display-API (nach Audit); CR-Stats per Hand | – |

## 7. Offene Prüfpunkte vor Phase 1
- [ ] CR Creator-ToS komplett: Scraping, Automatisierung, mehrere Accounts
- [ ] Whop-API: Kampagnen/Einreichungen für Creator?
- [ ] YouTube `videos.insert` aktuell: privat-Sperre für ungeprüfte Projekte?
- [ ] TikTok: Upload-in-Entwürfe ohne Audit möglich? Unoriginal-Regeln
- [ ] Gemini/Groq Gratis-Limits & Datennutzung
- [ ] Konkrete offene CR-Kampagnen der Wunsch-Streamer + deren Quellen-Freigaben

## Quellen
- [CR: Clipping payouts explained](https://contentrewards.com/articles/clipping-payouts-explained)
- [CR: Social media clipping explained](https://contentrewards.com/articles/social-media-clipping-explained)
- [CR: Creator Terms of Service](https://contentrewards.com/terms-of-service/clippers) · [Brand Terms](https://contentrewards.com/brands-terms)
- [Whop Docs: Content Rewards](https://docs.whop.com/manage-your-business/growth-marketing/content-rewards) · [Whop API: List Public Submissions (bounties)](https://docs.whop.com/api-reference/beta/bounties/list-public-submissions)
- [TikTok Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines) · [Direct Post API](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- [YouTube videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) · [YouTube Monetization policies](https://support.google.com/youtube/answer/1311392)
- [Instagram Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- [X API docs](https://docs.x.com/x-api/introduction)
- Drittquellen (⚠️): [reap.video](https://reap.video/blog/whop-clipping), [clipspeed.ai](https://www.clipspeed.ai/blog/can-you-clip-someone-elses-stream.html), [adaptlypost](https://adaptlypost.com/blog/tiktok-post-limit-per-day), [relevantaudience](https://www.relevantaudience.com/youtube/youtube-shorts-original-content-reach-update/), [postproxy X pricing](https://postproxy.dev/blog/x-api-pricing-2026), [Apify CR scraper](https://apify.com/tactful_anvil/whop-content-rewards-scraper)

## 8. Nachtrag Phase 1 – CR Creator-AGB gelesen (2026-11-17)
Quelle: [contentrewards.com/terms-of-service/clippers](https://contentrewards.com/terms-of-service/clippers) ✅
- **7.12 Einreichung binnen 30 Min. nach Veröffentlichung**, ältere Posts nicht einreichbar → Posten und Einreichen müssen gekoppelt sein (Phase 4: Benachrichtigung sofort nach Post).
- **7.11 Ein Post = eine Kampagne**; abgelehnter Post nirgends neu einreichbar.
- **12.9 Werbe-Hinweis (FTC) muss am Videoanfang stehen** → Hook-Overlay (Phase 2b) muss Platz dafür lassen.
- **12.11 Politische Clips nicht auf TikTok/X** → Kategorie „political“ ausgeschlossen.
- **13.3 Ein CR-Account pro Person**; 9.4 verbundene Accounts werden gemeinsam bewertet.
- **14.1/14.2** Social-Accounts per OAuth oder Bio-Code verbinden; CR liest nur, postet nicht.
- **8 Pre-post Review**: manche Kampagnen verlangen MP4-Entwurf vor dem Posten → Feld `prepost_review`.
- **6.1 CPM**: Mindest- und Höchstbetrag pro Clip; Raten ggf. je Zuschauerland. 6.11: Rate zum Einreichzeitpunkt gilt.
- **7.3** CPM-Runden: 7 Tage Verdienst + 3 Tage Halt.
- Zu Scraping/Automatisierung des CR-Zugangs: **kein Abschnitt gefunden**. robots.txt sperrt `/api/`. → Keine Nutzung interner CR-Endpunkte; Erfassung per kopiertem Seitentext (Issue-Formular).
- Whop-API: Endpunkte „bounties“ mit Ziel-Typ `clipping` existieren (Current API, Beta); ob CR-Kampagnen dort gelistet sind und ob Creator-Schlüssel Zugriff haben: **ungeprüft** (Doku-Abruf hier blockiert). Bis dahin Halbautomat.

## 9. Automatische Kampagnensuche (umgesetzt)
- **Quelle:** öffentliche Seiten `contentrewards.com/c/discover/clipping`, `/c/discover`, `/sitemap.xml`, `/c/campaigns/<id>` – ohne Login. robots.txt erlaubt sie (gesperrt nur `/api/`, `/home`, `/onboarding` …). Die Seiten liefern strukturierte Daten: Rate/Mindest-/Höchstauszahlung je Plattform, Budget/verbraucht, Status, Bewerbung nötig, Briefing („guidelines“), Pflicht-Flags (OAuth, Link in Bio, Logo, Pre-Approval), Statistik (genehmigte Clips, Views), Top-Clips.
- **Schonend:** `tools/discover.py` prüft robots.txt, nutzt nie `/api/`, 4 s Pause je Seite, max. 30 Detailseiten pro Lauf, alle 3 h (≈ 250 Seiten/Tag), eigener User-Agent.
- **Restrisiko:** CR-AGB enthalten kein Scraping-Verbot (gelesen, s. Abschnitt 8), aber CR kann das jederzeit ändern oder den Seitenaufbau umstellen → Parser meldet „keine Daten“, dann Issue-Formular als Rückfall.
- **Whop-API:** „Bounties“ (`GET /api/v1/bounties`, Ziel `clipping`) sind Festbetrag-pro-Gewinner-Aufgaben, **nicht** die CPM-Kampagnen von CR → für CR nicht nutzbar. ✅ (OpenAPI gelesen)
- **Beitreten:** braucht Login, keine API → bleibt ein Klick von Hand (Issue „Beitreten“ mit Häkchen). Ein Login-Bot wäre Browser-Automatisierung mit Konto – bewusst nicht gebaut.
- Keine Frist im Datenmodell von CR: Kampagnen enden über Budget/Status → Auto-Stopp darüber.
