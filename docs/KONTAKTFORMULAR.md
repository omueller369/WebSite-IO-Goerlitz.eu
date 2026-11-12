# Kontaktformular 0.1.1

Formularfelder: Name, E-Mail, Thema (Software / Rail Software / KI-Musik), Nachricht. Fester Empfänger und authentifizierter Absender: **info@io-goerlitz.eu**. Die Besucheradresse wird ausschließlich als Reply-To gesetzt; Empfänger oder SMTP-Header können nicht durch Besuchereingaben geändert werden.

Einrichtung über [INSTALL-UPDATE-0.1.1.md](INSTALL-UPDATE-0.1.1.md). Das Mailpostfach liegt auf dem vorhandenen Strato-Server; das Script richtet für dieses Konto keine Gmail-Weiterleitung ein. Vorhandene Weiterleitungen anderer CTL-Postfächer bleiben unberührt.

Der WSGI-Dienst in `server/contact.py` ist unabhängig von RailSoftware und benötigt keine Datenbank. Er läuft unter einem systemd-DynamicUser an `127.0.0.1:8091`. Apache ordnet ausschließlich `/website-contact` dorthin. Das Postfachpasswort wird bei der Einrichtung verdeckt abgefragt, in einer root-lesbaren Datei auf dem Server verwahrt und über systemd `LoadCredential` an den Prozess gegeben. Keine SMTP-Passwörter im Git, statischen Export oder Kommandozeilenargumenten.

- POST als JSON; nur von exakt `https://ctl-software.io-goerlitz.eu`, keine CORS-Freigaben, keine Cookies.
- Validierung, Größenlimit, feste Themen, Honeypot und Schutz vor Mail-Header-Injection.
- Fünf Anfragen pro IP-abgeleitetem HMAC-Wert und Stunde; global 100 pro Stunde. Nur RAM, keine persistente Nachrichtendatenbank. Abgelaufene Werte werden bei der nächsten Anfrage entfernt; Neustart löscht alle Werte.
- Genau ein Gunicorn-Worker mit vier Threads; bei mehreren Instanzen wäre eine gemeinsame Begrenzung erforderlich.
- TLS-validierte SMTP-Anmeldung. Bei Fehlern keine Erfolgsmeldung und keine Zugangsdaten in Antworten oder Logs.
- SMTP-Übernahme bestätigt keine externe Zustellung. Keine automatische Wiederholung bei unklarer Verbindung, um unbemerkte Duplikate zu vermeiden.
- Die Statusabfrage prüft vorhandene Konfiguration und lesbare Credentials, nicht die Live-Erreichbarkeit des SMTP-Servers. Beim Versand werden tatsächliche Fehler angezeigt.
- In Sites und anderen Hosts bleibt Versand gesperrt. Ohne JavaScript sind Telefon und E-Mail die Alternativen. Bei Änderung der Zieldomain beide Origin-Prüfungen in Frontend und Dienst anpassen.

Das Script testet das Postfach beim ersten Lauf durch eine lokale Testnachricht mit IMAP-Nachweis und DKIM-Signatur. Eine Formularanfrage nach der Veröffentlichung zusätzlich selbst testen; in der Entwicklungsumgebung wurden keine echten Nachrichten versendet.
