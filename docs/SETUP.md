# Einrichtung – einmalig, alles im Browser

Zugangsdaten nie in den Chat, nie ins Repo. Immer: **Repo → Settings → Secrets and variables → Actions → New repository secret**
(https://github.com/biceraras6-afk/stream-clips/settings/secrets/actions/new).

## 1. Privates Daten-Repo (Protokolle, Post-Links, Einreich-Hinweise)
1. https://github.com/new → Name `stream-clips-data` → **Private** → „Add a README“ anhaken → Create.
2. (Dort landen Protokolle und Einreich-Issues; Push kommt über Telegram, siehe 1b.)

## 1b. Push aufs Handy (Telegram, empfohlen)
GitHub benachrichtigt dich nicht über Issues, die mit deinem eigenen Schlüssel angelegt werden – deshalb Telegram.
1. Telegram öffnen → **@BotFather** → `/newbot` → Name z. B. „Clip Einreichen“ → Token kopieren → Secret `TELEGRAM_BOT_TOKEN`.
2. Deinem neuen Bot eine Nachricht schicken (z. B. „hi“).
3. Im Browser öffnen: `https://api.telegram.org/bot<TOKEN>/getUpdates` → bei `"chat":{"id":…}` die Zahl kopieren → Secret `TELEGRAM_CHAT_ID`.

## 2. GitHub-Schlüssel `GH_ADMIN_TOKEN`
Damit kann die Automatik Zugänge speichern und ins Daten-Repo schreiben.
1. https://github.com/settings/personal-access-tokens/new
2. Name `stream-clips`, Ablauf 1 Jahr, **Only select repositories:** `stream-clips` und `stream-clips-data`.
3. Repository permissions: **Secrets: Read and write**, **Contents: Read and write**, **Issues: Read and write**, **Actions: Read-only**.
4. Generate → Token kopieren → Secret `GH_ADMIN_TOKEN` anlegen.

## 3. YouTube (`yt1`)
Altes Google-Projekt wiederverwenden (dort war öffentliches Posten schon möglich).
1. https://console.cloud.google.com → altes Projekt → APIs & Dienste → Anmeldedaten → OAuth-Client (Typ **Desktop**).
   Ist es ein Web-Client: unter „Autorisierte Weiterleitungs-URIs“ `http://localhost` ergänzen.
2. Client-ID → Secret `YT1_CLIENT_ID`, Clientschlüssel → Secret `YT1_CLIENT_SECRET`.
3. Falls die App im Testmodus ist: OAuth-Zustimmungsbildschirm → Testnutzer → Google-Konto des neuen Kanals eintragen.
4. Actions → **auth** → Run workflow: account `yt1`, schritt `link` → im Lauf auf „Hier anmelden“ → mit dem Konto des **neuen Kanals** anmelden → Erlauben.
5. Die Seite danach lädt nicht (localhost) – **Adresse aus der Adresszeile kopieren**.
6. Actions → **auth** → Run workflow: account `yt1`, schritt `code`, code = die kopierte Adresse. Innerhalb weniger Minuten, der Code verfällt.

## 4. Instagram (`ig1`)
1. Instagram-App: Konto `@streamhighlights.daily` (Vorschlag) → Einstellungen → Kontotyp → **Professional (Creator)**.
2. https://developers.facebook.com/apps → App erstellen → Anwendungsfall **„Inhalte auf Instagram verwalten“** (Instagram API mit Instagram-Login).
3. In der App: Instagram → API-Einrichtung mit Instagram-Login:
   - Instagram-App-ID → Secret `IG1_APP_ID`, Instagram-App-Geheimschlüssel → Secret `IG1_APP_SECRET`
   - **Business-Login → Weiterleitungs-URL:** `https://github.com/biceraras6-afk/stream-clips`
   - Rollen → Instagram-Tester: dein Instagram-Konto hinzufügen, in der Instagram-App Einladung annehmen (Einstellungen → Website-Berechtigungen → Tester-Einladungen).
4. Actions → **auth**: account `ig1`, schritt `link` → anmelden → Erlauben → du landest auf der GitHub-Repo-Seite; **Adresse kopieren** (enthält `code=`).
5. Actions → **auth**: account `ig1`, schritt `code`, code = Adresse.
Der Token gilt 60 Tage und wird montags automatisch erneuert (Workflow „tokens“).

## 5. TikTok (`tt1`)
1. https://developers.tiktok.com → Manage apps → App anlegen.
2. Produkte: **Login Kit** und **Content Posting API** (nur „Upload“, nicht „Direct Post“). Scopes: `user.info.basic`, `video.upload`, `video.list`.
3. Redirect URI: `https://github.com/biceraras6-afk/stream-clips`.
4. Client key → Secret `TT1_CLIENT_KEY`, Client secret → Secret `TT1_CLIENT_SECRET`.
5. App zur Prüfung einreichen (Begründung: „Upload my own edited stream clips as drafts to my own account; I publish manually in the app.“). Bis zur Freigabe: unter **Sandbox** dein TikTok-Konto als Testnutzer eintragen.
6. Nach Freigabe: Actions → **auth**: account `tt1`, schritt `link` → anmelden → Adresse kopieren → schritt `code`.
Videos landen als **Entwurf** in deiner TikTok-App; du postest dort (Text liegt fertig im Einreich-Issue).

## 6. Kampagnen
Dashboard → „Beitritte abhaken“: Kampagne öffnen → Join → im Issue abhaken. Dann: Actions → **clips** → Run workflow (`auto`).
Bei Content Rewards deine Social-Accounts verbinden (manche Kampagnen verlangen OAuth-Verbindung).

## Täglich danach
- Push „Einreichen bis HH:MM“ → Link öffnen → bei Content Rewards **Submit** → Issue schließen.
- TikTok: Entwurf in der App posten, dann einreichen.
- Neue Kampagnen im Issue „Beitreten“ abhaken.
