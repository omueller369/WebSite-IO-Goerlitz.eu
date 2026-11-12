# Separater Kontaktversand auf dem Strato-Server

Die Website bleibt statisch exportierbar. Nur der Formularversand nutzt einen separaten, kleinen Python-WSGI-Dienst; er ist unabhängig von RailSoftware und dessen Datenbank. Empfänger ist fest `omueller369@gmail.com`. SMTP-Zugangsdaten werden ausschließlich auf dem Server eingerichtet, niemals im Chat, Repository oder statischen Export.

## Installation (Debian/Apache)

1. Freien Loopback-Port 8091 prüfen. Auf dem Server `sudo apt install python3-gunicorn` installieren. Der Paketpfad `/usr/bin/gunicorn` ist mit der Unit abzugleichen.
2. `server/contact.py` nach `/opt/io-website-contact/contact.py` kopieren. Dateien müssen für den Dienst lesbar und dürfen für ihn nicht schreibbar sein. In der Unit wird `DynamicUser=yes` verwendet.
3. `/etc/io-website/` als root anlegen und `server/contact.env.example` nach `/etc/io-website/contact.env` kopieren. Nur root darf die Datei lesen (`chmod 600`). Echte Werte für SMTP_HOST, SMTP_FROM und ggf. SMTP_USERNAME/SMTP_PASSWORD eintragen. SMTP_FROM muss beim Anbieter als Absender zugelassen sein. Ausschließlich TLS: `starttls`/587 oder `ssl`/465. Keine Google-Passwörter oder sonstigen Zugangsdaten aus dem Kontakt-Empfänger ableiten; der Versanddienst kann ein anderes geeignetes SMTP-Postfach nutzen.
4. `server/io-website-contact.service` nach `/etc/systemd/system/` kopieren. `sudo systemctl daemon-reload` und `sudo systemctl enable --now io-website-contact` ausführen.
5. Auf dem Server `curl http://127.0.0.1:8091/website-contact` prüfen. Nur bei konfiguriertem Dienst erscheint `available: true`.
6. Apache-Module `proxy`, `proxy_http`, `headers` aktivieren. `apache-contact.conf.example` im bestehenden HTTPS-VirtualHost VOR der allgemeinen Backend-Regel einfügen. Den neuen Pfad `/website-contact` zuvor auf bestehende Nutzung prüfen. Apache überschreibt `X-Website-IP` mit der tatsächlichen Client-IP; bei weiteren vorgeschalteten Proxys muss die reale IP-Konfiguration vertrauenswürdig eingerichtet werden. Kein direkter externer Zugang zu Port 8091.
7. `sudo apache2ctl configtest` und nur bei Erfolg Reload ausführen. Formularstatus über HTTPS prüfen. Dann eine ausdrücklich als Test erkennbare Anfrage absenden und Eingang im Empfängerpostfach kontrollieren. Hier in der Entwicklung wurden keine echten E-Mails versendet.

## Verhalten

- POST mit JSON, nur von exakt `https://ctl-software.io-goerlitz.eu`; keine CORS-Freigaben und keine Cookies.
- Feste Themenauswahl, E-Mail-Prüfung, Längenbegrenzungen, Honeypot, Header-Injection-Schutz. SMTP-Fehler führen niemals zu einer Erfolgsmeldung.
- Höchstens fünf Anfragen pro IP-abgeleitetem Wert und Stunde, global 100 pro Stunde. Werte werden mit zufälligem HMAC-Schlüssel nur im RAM gehalten und nach Ablauf einer Stunde bei der nächsten Formularanfrage entfernt. Neustart setzt die Begrenzung zurück; die Unit verwendet absichtlich genau einen Worker mit vier Threads. Bei mehreren Instanzen braucht es eine gemeinsame Begrenzung.
- Keine eigene Nachrichtendatenbank, keine Request-Body-Logs. Apache kann dennoch Zugriffsprotokolle anlegen; Aufbewahrung vor Freigabe festlegen.
- SMTP-Übernahme ist keine Garantie für die Zustellung. Es gibt keine automatische Wiederholung, um unbemerkte Duplikate zu vermeiden. Bei Verbindungsabbruch kann die tatsächliche Übergabe unklar sein; die Oberfläche meldet das entsprechend.
- Die Statusabfrage prüft Konfiguration, nicht SMTP-Erreichbarkeit. Bei SMTP-Ausfall erscheint beim Absenden eine Fehlermeldung.
- Ohne JavaScript bitte den E-Mail-/Telefonkontakt nutzen. Die private Sites-Vorschau bleibt ohne Versand. Bei Änderung der Zieldomain sind Origin in `server/contact.py` und `src/website-assets/site.js` anzupassen.

Vor Aktivierung: Gmail-Verwendung, Drittlandgrundlage und Aufbewahrung mit der Datenschutzerklärung abgleichen; siehe REDAKTION.md. Das bestehende RailSoftware-SMTP wird nicht verändert.
