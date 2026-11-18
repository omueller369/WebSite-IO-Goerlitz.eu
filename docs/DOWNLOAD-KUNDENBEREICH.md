> Erscheinungsbild 0.3.0: neues IO-Logo und Weinrot/Dunkelblau auch im geschützten Bereich. Auf dem eingerichteten Server mit `sudo io-website update --ref v0.3.0` übernehmen.

# Download und Kundenverwaltung · Version 0.2.2

Öffentliche Präsentationsseiten bleiben statisch exportierbar. Download-Anmeldung und Kundenverwaltung laufen in einem getrennten Serverdienst mit eigener SQLite-Datenbank. Keine Kopplung an TF-Konten, die RailSoftware-Datenbank oder Postfachpasswörter.

## Server-Update von 0.1.x

**Für dieses Funktionsupdate zuerst die neue Script-Datei herunterladen.** Der ältere Installer kann den zusätzlichen Dienst noch nicht einrichten.

```sh
curl -fL https://raw.githubusercontent.com/omueller369/WebSite-IO-Goerlitz.eu/v0.2.2/deploy/io-website.py -o io-website.py
sudo python3 io-website.py update --ref v0.2.2
```

Ist die vorherige Installation noch nicht erfolgreich abgeschlossen, stattdessen `sudo python3 io-website.py install --ref v0.2.2` ausführen. Die bekannte Mail-/DNS-Vorprüfung gilt weiterhin. Bei einer funktionierenden Installation genügt `update`; keine neuen DNS-Einträge nötig.

Der neue Installer fragt bei erstmaliger Einrichtung das Download-Admin-Passwort zweimal verdeckt im Terminal ab:

- E-Mail: **omueller369@gmail.com**
- Eigenes Passwort mit 12 bis 256 Zeichen, unabhängig vom Mailpostfach und von RailSoftware.
- Keine Passwörter im Chat, GitHub oder als Kommandozeilenparameter.

Es wird nur ein gesalzener scrypt-Hash in `/etc/io-website/download-admin.json` gespeichert (0600, root). systemd übergibt die Datei als Credential an den unprivilegierten Download-Dienst. Bereits eingerichtete Admin-Daten bleiben bei weiteren Updates erhalten; es gibt kein Standardpasswort.

## Anmeldung und Freigaben

1. `https://ctl-software.io-goerlitz.eu/download/` öffnen; der Link steht im Kopf jeder öffentlichen Seite.
2. Als Admin mit der oben genannten E-Mail und dem bei der Einrichtung gewählten Passwort anmelden.
3. Über **Kundenverwaltung** zu `https://ctl-software.io-goerlitz.eu/kundenverwaltung/` wechseln. Ausschließlich das Admin-Konto erhält Zugriff. Der bisherige RailSoftware-Pfad `/admin` bleibt unverändert.
4. Kundenname, E-Mail und ein Startpasswort zweimal eingeben. **Konto anlegen und freischalten** aktiviert den Zugang.
5. Startpasswort persönlich über einen geeigneten getrennten Kanal übermitteln. Es gibt keine automatische Registrierungs-/Freigabe-E-Mail und keine öffentliche Selbstregistrierung.
6. Der Kunde meldet sich an und muss das Startpasswort vor seinem ersten Download ändern. Danach kann er den aktuellen Android-Link öffnen und sein eigenes Passwort ändern.

Pro Kunde kann der Admin den Zugang sperren, wieder freischalten oder ein neues Startpasswort setzen. Sperre und Passwort-Zurücksetzung widerrufen vorhandene Kundensitzungen sofort. Passwort-Zurücksetzung erzwingt erneut einen eigenen Passwortwechsel. Die Admin-Identität kann über die Kundenformulare weder überschrieben noch gesperrt werden.

## Aktueller Android-Link

Standardmäßig ermittelt der Dienst den neuesten veröffentlichten Release mit APK im öffentlichen Repository `omueller369/RailSoftware`, einschließlich Test-/Vorabversionen mit entsprechender Kennzeichnung. Die Prüfung erfolgt bei einem angemeldeten Abruf höchstens einmal pro Stunde; betrachtet werden die 20 neuesten Releases. Bei GitHub-Ausfall bleibt der zuletzt bekannte Link erhalten.

Die erste hinterlegte Fassung ist TF Portal Android 0.26.52 Test 22. Die spätere automatische Ermittlung liest nur öffentliche Release-Metadaten und sendet keine Kunden- oder Anmeldedaten an GitHub. Website- und Softwarepflege bleiben in getrennten Repositories.

In der Kundenverwaltung kann der Admin eine eigene Versionsbezeichnung und HTTPS-Adresse speichern. Dadurch wechselt die Auswahl in den manuellen Modus. **Aktuellen Link aus GitHub übernehmen und Automatik aktivieren** stellt die automatische Auswahl wieder her.

Die Downloadseite und ihre Weiterleitung sind geschützt. **Eine bereits öffentliche APK auf GitHub bleibt außerhalb dieser Website öffentlich abrufbar.** Der Schutz dieser Seite ändert keine Freigaben des RailSoftware-Repositories und erzeugt keine geschützte Demo.

## Admin-Passwort ändern

Nach dem erfolgreichen Update:

```sh
sudo io-website admin-password
```

Neue verdeckte Abfrage; das Mailpostfachpasswort bleibt unverändert. Beim Neustart bzw. nächsten Abruf übernimmt der Dienst den neuen Hash und widerruft bisherige Admin-Sitzungen. Kundenpasswörter werden dadurch nicht geändert.

## Dienste, Daten und Sicherung

- Unit: `io-website-downloads.service`.
- Port: `127.0.0.1:8092`, ausschließlich lokal. Apache übernimmt TLS und leitet nur `/download` und `/kundenverwaltung` mit ihren Unterpfaden an diesen Dienst.
- Runtime-Code: `/opt/io-website-contact/downloads.py`; eigenes Gunicorn-Modul über `/usr/bin/python3 -m gunicorn`.
- Kundendaten, Passwort-Hashes, Freigaben, Sitzungen, Link-Konfiguration und Anmeldeschutz: `/var/lib/io-website-downloads/downloads.sqlite3`. systemd kann den StateDirectory intern auf `/var/lib/private/io-website-downloads` abbilden.
- Der Dienst hat Schreibzugriff auf sein eigenes StateDirectory; kein Schreibzugriff auf Website-Dateien oder das RailSoftware-Repository. Keine Klartext-Passwörter in der Kundendatenbank.
- Die Datenbank und das root-geschützte Admin-Credential zusätzlich zur vorhandenen Serversicherung sichern. Für eine einfache Dateisicherung den Download-Dienst kurz stoppen oder die SQLite-Backup-Funktion verwenden; nicht während eines Schreibvorgangs unkoordiniert kopieren. Sicherungen mit Kundendaten vertraulich verwahren.

Updates ersetzen weder Kundendaten noch Freigaben oder manuell gespeicherte Links. Der Website-Rollback stellt den passenden Download-Code und die Unit mit wieder her. Beim Rückweg auf eine ältere Version ohne Downloadbereich wird der neue Dienst abgeschaltet; die Kundendaten bleiben für ein späteres Update erhalten. Datenbankschema 1 wird ausschließlich additiv initialisiert.

## Zugriffsschutz

Serverseitige Rollenprüfung für jede Admin-Aktion, kurzlebige Sitzungscookies (`Secure`, `HttpOnly`, `SameSite=Strict`, hostgebunden), acht Stunden maximale Sitzungsdauer, Sitzungsrotation bei Anmeldung, CSRF- und Origin-Prüfung für sämtliche Formulare, Anmeldelimits pro Netzwerkadresse und E-Mail sowie global. Session-Tokens liegen nur gehasht in SQLite. Authentifizierte Antworten werden nicht gecacht und nicht von Suchmaschinen indiziert.

Notwendige Cookies und Kontoverarbeitung sind in der Datenschutzerklärung ergänzt. Keine Tracking-Cookies. Kundendaten werden nicht in den statischen Export geschrieben. Die private Sites-Vorschau zeigt nur Hinweise auf den Bereich; sie nimmt keine Zugangsdaten entgegen und bietet keine Kundenverwaltung.

## Kontrollen auf dem Server

```sh
sudo io-website status
sudo systemctl status io-website-downloads --no-pager -l
sudo journalctl -u io-website-downloads -n 60 --no-pager
```

Nach dem Update Admin-Anmeldung, Kundenanlage, ersten Passwortwechsel, normalen Download, Sperre und Wiederfreigabe mit einem Testkunden prüfen. Der Installer kontrolliert zusätzlich, dass ein anonymer Zugriff auf die Verwaltungsseite zur Anmeldung führt. TLS-Zertifikat und ursprüngliche Portal-/API-Routen bleiben erhalten.

## Login-Korrektur 0.2.1

Die geschützten Seiten verwenden `Referrer-Policy: same-origin`, damit Browser eigene Formular-Anmeldungen nicht durch eine unterdrückte Herkunft blockieren. Bei fehlendem Origin-Header werden ausschließlich eine passende HTTPS-Referer-Adresse oder browserseitige Same-Origin-Metadaten akzeptiert; CSRF-Prüfungen bleiben erforderlich. Explizites `Origin: null`, fremde Ursprünge und nicht prüfbare Anfragen werden abgewiesen. Nach dem Update die Anmeldeseite neu laden. Konten und Passwörter bleiben erhalten.

## Layout-Korrektur 0.2.2

Der geschützte Bereich verwendet einen eigenen zentrierten Container ohne die breitenabhängigen Außenabstände der Präsentationsseiten. Damit bleiben Download-Karte, Überschriften und Formulare auch auf Ultrawide-Monitoren ausreichend breit. Der HTML-Link enthält eine CSS-Versionsnummer, damit Browser die neue Layout-Datei abrufen. Login und Kundendaten bleiben unverändert.
