# Änderungen

## 0.2.1

- Behebt „Ungültiger Ursprung“ bei Formular-Anmeldungen durch `Referrer-Policy: same-origin`.
- Sichere Herkunftsprüfung bei fehlendem Origin-Header über passende Referer- oder Fetch-Metadata-Angaben; CSRF-Schutz bleibt bestehen.
- Fremde und explizit unbekannte Ursprünge bleiben gesperrt. Keine Änderungen an bestehenden Konten oder Passwörtern.


## 0.2.0

- Download-Link in der Kopfzeile und serverseitig geschützter Downloadbereich.
- Admin-Konto `omueller369@gmail.com`; verdeckte Passwortabfrage im aktualisierten Installations-/Update-Script.
- Nur für den Admin erreichbare Kundenverwaltung mit Kontenanlage, Sperre, Freischaltung und Passwort-Zurücksetzung.
- Erster Passwortwechsel für Kunden, widerrufbare Sitzungen, CSRF-Schutz und begrenzte Anmeldeversuche.
- Aktueller Android-Link automatisch aus GitHub-Releases (inklusive gekennzeichneter Testversionen), alternativ manuell durch den Admin.
- Eigener unprivilegierter Download-Dienst mit persistenter SQLite-Datenbank; getrennt von RailSoftware und Mailkonten.
- Passende Runtime-Sicherung für Website-Rollbacks sowie ergänzte Datenschutztexte.


## Installer 0.1.2 (Website bleibt 0.1.1)

- Gunicorn-Start über `/usr/bin/python3 -m gunicorn`, ohne CLI-Wrapper vorauszusetzen.
- Prüfung von Import und Modulstart mit genau dem System-Python vor Postfachänderungen.
- Fortsetzen mit `install --ref v0.1.2`; bereits angelegtes Postfach und Passwort bleiben erhalten.


## 0.1.1

- Eigenständige IO-Software-Görlitz-Präsentation mit Softwareleistungen, KI-Musik und Rail-Software-Produktübersicht.
- Kontaktadresse und Formularzustellung auf `info@io-goerlitz.eu`, Speicherung auf dem eigenen Server.
- Komplettes GitHub-Installations-/Update-Script mit DNS-Vorprüfung, verdeckter Postfachpasswortabfrage, lokalem Zustelltest, Release-Umschaltung, Status, Passwortwechsel und Website-Rollback.
- Additive Integration in den vorhandenen CTL-Postfix-/Dovecot-2.4-/OpenDKIM-/PostSRSd-Stack; bestehende Mitarbeiterkonten bleiben erhalten.
- SMTP-Geheimnis ausschließlich auf dem Server, Übergabe an den unprivilegierten Kontaktprozess über systemd Credentials.
- Impressum, Datenschutzerklärung, SVG-Logo und separat exportierbare statische Dateien.
- Persönliche Demo-Konten, Demo und Downloads sind noch nicht freigeschaltet. Keine öffentlichen Portal-Links.
