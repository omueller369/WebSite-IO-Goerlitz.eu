# Version 0.1.1: Website, Postfach und Updates

Das eigenständige Projekt `omueller369/WebSite-IO-Goerlitz.eu` wird unter **https://ctl-software.io-goerlitz.eu/** veröffentlicht. Das Postfach **info@io-goerlitz.eu** wird auf dem vorhandenen Server ergänzt. RailSoftware-Repository, Datenbank und Anwendung werden nicht aktualisiert oder neu gestartet.

## Passende Serverumgebung

Die Routine ist auf den in `omueller369/RailSoftware`, Branch `fix/language-picker-reload`, Commit `01446767cf4eb1438fbf86e317ca26b21b08f51e` dokumentierten Stand abgestimmt: Ubuntu 26.04, Apache, Postfix, Dovecot **2.4**, OpenDKIM, PostSRSd, `ctlvmail`, Maildir unter `/var/vmail`, Tabellen `ctl-users`/`ctl-domains`/`ctl-mailboxes` und VirtualHost `/etc/apache2/sites-available/ctlsoftware-test.conf`.

Das ist kein Neuinstallationsscript für einen leeren Server und kein ISPConfig-/Plesk-Installer. Bei einer abweichenden Konfiguration stoppt es vor der Umschaltung. Die vorhandene RailSoftware-Komplettinstallation darf hierfür **nicht** erneut ausgeführt werden: sie kann Mail- und Apache-Konfiguration neu erzeugen.

## 1. Einzelne Datei herunterladen und prüfen

Auf dem Zielserver in einem administrativen Arbeitsverzeichnis:

```sh
curl -fL https://raw.githubusercontent.com/omueller369/WebSite-IO-Goerlitz.eu/v0.1.1/deploy/io-website.py -o io-website.py
python3 io-website.py plan
```

Die Datei vor dem privilegierten Start ansehen. Kein `curl | sudo bash`. Das Script enthält die vollständige Installations- und Update-Logik; der Website-Quellstand wird beim Start direkt aus GitHub geladen. Keine GitHub-Anmeldung nötig, da das Website-Repository öffentlich ist.

## 2. Erster Lauf: DNS vorbereiten

```sh
sudo python3 io-website.py install --ref v0.1.1
```

Die Routine prüft die vorhandenen Dienste, erzeugt einen eigenen DKIM-Schlüssel und gibt die nötigen STRATO-DNS-Werte aus. Sie speichert die Werte in `/etc/io-website/dns-required.txt`. Solange DNS nicht passt, stoppt sie **vor Postfach-Erstellung und Website-Umschaltung**. Ein Abbruch an dieser Stelle ist vorgesehen; nach Korrektur denselben Befehl erneut ausführen.

In der STRATO-DNS-Verwaltung für **io-goerlitz.eu**:

| Typ | Name | Wert |
| --- | --- | --- |
| MX | @ / Hauptdomain | Priorität 10, `ctl-software.io-goerlitz.eu.` |
| TXT | @ / Hauptdomain | ein einzelner SPF-Eintrag mit `ip4:212.227.86.251`, z. B. `v=spf1 ip4:212.227.86.251 -all` |
| TXT | `io._domainkey` | individueller Wert aus dem Script |
| TXT | `_dmarc` | z. B. `v=DMARC1; p=none; rua=mailto:info@io-goerlitz.eu` |

**Bestehende Mailnutzung der Hauptdomain beachten:** Eine MX-Änderung betrifft eingehende E-Mails für die gesamte Domain, nicht nur `info`. Vorhandene Postfächer bei einem anderen Anbieter müssen vor der Umstellung migriert bzw. in die Planung einbezogen werden. Bestehende SPF-/DMARC-Regeln zusammenführen, keine zweiten SPF-Einträge anlegen. Das Script nimmt keine DNS-Änderung vor. Bestehende DNS-Einträge der CTL-Subdomain bleiben erhalten.

Der vorhandene Mailhost benötigt weiterhin A `212.227.86.251`, den passenden PTR und sein gültiges TLS-Zertifikat. Wegen des dokumentierten IPv4-Mailbetriebs darf kein unversorgtes AAAA am Mailhost bestehen. Die IP ist aus dem Projektstand übernommen; bei geändertem Server `--ipv4 NEUE_IP` angeben. Die Hauptdomain benötigt für das Postfach keinen neuen Webserver-VirtualHost und kein eigenes Mail-TLS-Zertifikat: Clients verbinden sich mit dem vorhandenen TLS-Host.

Geprüft werden beide öffentlichen Resolver `1.1.1.1` und `8.8.8.8`. DNS-Verteilung kann Zeit benötigen. Die STRATO-Nameserver bleiben zuständig.

## 3. Fortsetzen und Passwort eingeben

Denselben Installationsbefehl erneut ausführen. Wenn alle DNS-Prüfungen passen, fragt das Script das neue Postfachpasswort **zweimal verdeckt im Terminal** ab; mindestens zwölf Zeichen. Kein voreingestelltes Passwort. Nicht im Chat oder als Kommandozeilenparameter eingeben.

Das Passwort wird für Dovecot mit SHA512-CRYPT gehasht. Die für den automatischen Formularversand notwendige Zugangskopie liegt ausschließlich unter `/etc/io-website/contact-password`, root-lesbar mit Modus 0600. Der unprivilegierte Formularprozess erhält sie über systemd `LoadCredential`, nicht über Prozessargumente oder eine öffentliche `.env`. Die Datei und Maildaten gehören in die geschützte Serversicherung.

Die Routine führt anschließend aus:

1. Eigenes virtuelles Postfach mit Maildir anlegen; vorhandene Konten behalten.
2. Eigene Postfix-Domain-/Empfängertabellen ergänzen und DKIM für `io-goerlitz.eu` einbinden. Vorhandene Mitarbeiter-Mailtabellen und SRS-Einstellungen erhalten.
3. Prüfen, dass die dokumentierte Sieve-Weiterleitung das neue Postfach nicht erfasst. Für `info@io-goerlitz.eu` wird **keine Gmail-Weiterleitung** angelegt. Unbekannte globale Weiterleitungen oder BCC-Regeln führen zum Abbruch.
4. TLS-Anmeldung an SMTP/IMAP testen. Beim ersten erfolgreichen Lauf eine lokale Testnachricht von `info` an `info` senden, im Postfach nachweisen und DKIM-Domainsignatur kontrollieren. Diese Nachricht bleibt zur Kontrolle im Postfach; keine Testnachricht geht an einen externen Empfänger.
5. Website-Quellstand aus GitHub laden und statische Dateien in ein neues Release-Verzeichnis kopieren. Es werden keine Build-Scripte aus GitHub als root ausgeführt.
6. Getrennten Formular-Maildienst einrichten; bei Bedarf nur `python3-gunicorn` aus Ubuntu-Paketen ergänzen. Port 8091 bleibt ausschließlich an Loopback.
7. Bestehenden HTTPS-VirtualHost um ein eng begrenztes Include vor den Proxy-Regeln ergänzen. TLS, Software-Backend, phpMyAdmin und vorhandener Webmailer bleiben bestehen und werden nicht öffentlich verlinkt.
8. Apache-Konfiguration prüfen, Website umschalten, ausgewählte bestehende Software-Routen vor/nach der Umschaltung vergleichen und neue Seiten testen. Bei Fehlern Website, Kontaktcode und Apache-Konfiguration zurücksetzen. Das unabhängig angelegte Postfach und bereits empfangene Nachrichten werden dabei nicht gelöscht.

Erfolg wird erst mit `Online: https://ctl-software.io-goerlitz.eu/ — Version 0.1.1 (...)` gemeldet. Diese Meldung bestätigt den eigenen Serverlauf; die private Sites-Vorschau allein ist keine Server-Veröffentlichung.

## 4. Nutzung des neuen Postfachs

| Einstellung | Wert |
| --- | --- |
| Adresse / Benutzername | `info@io-goerlitz.eu` |
| Passwort | bei der Erstellung eingegeben |
| IMAP-Host | `ctl-software.io-goerlitz.eu` |
| IMAP-Port | 993, TLS/SSL |
| SMTP-Host | `ctl-software.io-goerlitz.eu` |
| SMTP-Port | 587, STARTTLS und Anmeldung |

Das vorhandene Roundcube kann mit der vollständigen Adresse und diesem Passwort genutzt werden; kein neuer Webmailer wird installiert. Ein externer Mailclient ist ebenfalls möglich. Danach einen externen Empfangs- und Antworttest vornehmen: der lokale Test kann die Annahme und Spam-Einstufung bei fremden Anbietern nicht beweisen.

## 5. Updates, Status und Rückweg

Nach erfolgreicher Installation liegt die geprüfte Routine unter `/usr/local/sbin/io-website`:

```sh
sudo io-website status
sudo io-website update
```

`update` lädt das neueste veröffentlichte GitHub-Release, also keine Drafts oder Vorabversionen. Für einen bestimmten Stand:

```sh
sudo io-website update --ref v0.1.1
```

Ein bewusst gewählter Branch ist mit `--ref main` möglich. Normale Updates ändern weder Postfachpasswort noch bestehende Maildaten. Die zum jeweiligen Commit gehörende Installationsroutine wird für folgende Aufrufe mit aktualisiert. Bei anderen VirtualHost-Pfaden `--vhost /etc/apache2/sites-available/DEINE.conf` angeben; vorhandene `sites-enabled`-Symlinks nicht als Schreibziel verwenden.

Zur vorherigen **Website-/Kontakt-Version** zurück:

```sh
sudo io-website rollback
```

Der Rollback stellt statische Dateien, den passenden Kontaktcode, die Unit und das Website-Apache-Fragment wieder her. Er verändert kein Mailpasswort und keine Nachrichten. Beim ersten Release ohne Vorgänger gibt es keinen Release-Rollback; die Erstinstallation stellt bei Fehlern automatisch die gesicherte Apache-Konfiguration wieder her.

Postfachpasswort später ändern:

```sh
sudo io-website mail-password
```

Erneut verdeckte Abfrage; Dovecot-Hash und Formularzugang werden gemeinsam aktualisiert. Bei Prüfungsausfall wird der vorherige Stand wiederhergestellt.

## Vorhandener CTL-Mailprovisioner

Er kann seine Tabellen bei Mitarbeiteränderungen neu schreiben. Die Website nutzt deshalb eigene Postfix-Tabellen. Für OpenDKIM werden die CTL-Signiertabellen und die Website-Domain in getrennte gemeinsame Lesetabellen zusammengeführt. Ein additiver Drop-in an `ctl-mailboxes.service` aktualisiert diese nach dessen Abschluss. Die gleiche Dateisperre wie im vorhandenen Provisioner verhindert verlorene Kontoänderungen. Unveränderte Tabellen lösen dabei keinen erneuten Maildienst-Neustart aus.

Die Domain `io-goerlitz.eu` nicht zusätzlich als von CTL verwaltete Mitarbeiterdomain anlegen. Die Website benötigt keinen Eintrag in der RailSoftware-Datenbank. Falls die komplette CTL-Serverinstallation später Apache-/Mail-Hauptkonfiguration neu erzeugt, `sudo io-website install --ref v0.1.1` zur Prüfung/Wiederanbindung nutzen; bei unbekannten Konfigurationen abbrechen und abgleichen.

## Dateien und Sicherungen

- Statische Releases: `/var/www/rail-website/releases/`; aktiver Symlink: `current`.
- Status, Website-Konfiguration und Geheimnis: `/etc/io-website/` (0700).
- Konfigurationssicherungen und zugehörige Kontaktcode-Versionen: `/var/lib/io-website/` (0700).
- Maildir: `/var/vmail/io-goerlitz.eu/info/Maildir/`.
- Dovecot-Zugang: zusätzliche Zeile in `/etc/dovecot/ctl-users`, alle anderen Zeilen erhalten.
- Eigene Postfix-Tabellen: `/etc/postfix/io-website-domains` und `io-website-mailboxes`.
- DKIM-Schlüssel: `/etc/opendkim/keys/io-goerlitz.eu/io.private`, nicht veröffentlichen.
- Getrennte Website-Zugriffslogs: `/var/log/apache2/io-website-access.log`, tägliche Rotation, sieben Tage; kein Querystring, Formularinhalt, Referrer oder User-Agent im Website-Log. Vorhandene Backend-Zugriffslogs bleiben separat erhalten.

Das Script löscht keine alten Releases oder Nachrichten automatisch. Serversicherung muss Konfiguration, Geheimnis, Maildir und DKIM-Schlüssel erfassen. Installations- und Update-Aufrufe sind gegeneinander gesperrt. Bei einem abgebrochenen Lauf denselben Aufruf wiederholen; ein bereits erfolgreich verwaltetes Postfach wird wiederverwendet, nicht überschrieben.

## Prüfgrenzen

Entwicklungstests prüfen Konfigurationszusammenführung, Erhalt bestehender Konten, unbekannte Sieve-/VirtualHost-Konfigurationen, Symlink-Abwehr, Rollback der Dateien sowie Formularvalidierung und SMTP-Fehler. Ein realer Strato-Lauf kann nur auf dem Zielserver mit dessen Diensten, Zertifikat und DNS erfolgen. Vor der öffentlichen Nutzung Impressum, Betreiberstatus und tatsächliche Datenschutzkonfiguration mit den bereitgestellten Texten abgleichen; siehe REDAKTION.md.
