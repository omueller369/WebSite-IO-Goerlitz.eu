# Getrennte Server-Veröffentlichung

Ziel: https://ctl-software.io-goerlitz.eu/ · Version 0.1.1

**Die vollständige Installations- und Update-Anleitung steht in [INSTALL-UPDATE-0.1.1.md](INSTALL-UPDATE-0.1.1.md).** Das zugehörige Script ist [deploy/io-website.py](../deploy/io-website.py).

Die Website und ihr Kontakt-Maildienst liegen im eigenen Repository. Es wird keine RailSoftware-Komplettinstallation gestartet und keine Anwendungsdatenbank geändert. Das vorhandene Mail-/Apache-System wird an genau begrenzten Stellen ergänzt.

## Routing-Vertrag

Nur `/`, `/index.html`, die explizit im [Website-Fragment](apache-website.conf.example) aufgelisteten Präsentationsseiten und `/website-assets/` gehen zum statischen Export. `/website-contact` erhält einen eigenen Loopback-Maildienst nach dem [Kontaktfragment](apache-contact.conf.example).

Alle sonstigen Routen bleiben bei den vorhandenen Regeln. Das betrifft insbesondere `/tf`, `/admin`, sämtliche Software-APIs, Anmelde-, Installations-, PWA-, Lokalisierungs- und Downloadpfade sowie den vorhandenen Webmailer und phpMyAdmin. Keine öffentlichen Links zu TF, Verwaltung oder Infrastrukturwerkzeugen. Kein Catch-all und kein SPA-Fallback. Unbekannte Unterpfade bleiben beim bisherigen Backend.

## DNS und HTTPS

Die Website bleibt auf dem vorhandenen HTTPS-Host und verwendet sein bestehendes Zertifikat. Keine DNS-Umschaltung auf Sites: Sites ist die getrennte private Vorschau. Die neuen Hauptdomain-Mail-DNS-Einträge betreffen `info@io-goerlitz.eu` und sind in der vollständigen Anleitung beschrieben.

## Release und Rückweg

Das Script sichert geänderte Konfigurationen, prüft Apache vor dem Reload, vergleicht ausgewählte Software-Routen und schaltet ein separates Release-Verzeichnis atomar um. Bei einem fehlgeschlagenen Website-Lauf wird die vorherige Website-/Kontakt-Konfiguration wiederhergestellt. Das angelegte Postfach und bereits gespeicherte Nachrichten bleiben erhalten. Ein späterer `rollback` setzt Website und passenden Kontaktcode auf das vorherige Release zurück; er löscht keine Maildaten.

## Abnahme

Nach der Installation Website auf Desktop und Mobilgerät prüfen, eine Kontaktanfrage senden und beantworten sowie TF-/Admin-Anmeldung, PWA und betriebliche Abläufe mit einem Testkonto kontrollieren. Auch einen Browser mit bereits installiertem Portal-Service-Worker verwenden: ein vorhandener Root-Scope-Cache kann eine ältere Startseite anzeigen. Der Installer entfernt oder verändert keine vorhandenen Software-Service-Worker.

Die Server-Konfiguration muss zum dokumentierten RailSoftware-Stand passen; bei Abweichungen stoppt die Routine. Eine generische PHP-/Plesk-/ISPConfig-Installation wird nicht automatisch angepasst.
