# IO-Software-Görlitz · Website 0.1.1

Eigenständiges Sites-Projekt „Rail Software Website“. Pflegebasis: `omueller369/WebSite-IO-Goerlitz.eu`, unabhängig vom Repository `omueller369/RailSoftware`.

## Installation und Updates

**[Vollständige Anleitung für Version 0.1.1](docs/INSTALL-UPDATE-0.1.1.md)** · [Komplettes Installationsscript](deploy/io-website.py)

Die Routine lädt die Website aus GitHub, ergänzt das Postfach `info@io-goerlitz.eu` in der vorhandenen CTL-Server-Mailumgebung und fragt sein Passwort bei der Erstellung verdeckt ab. Sie enthält DNS-Prüfung, Erstinstallation, Updates, Passwortwechsel, Status und Website-Rollback. Sie ist auf den dokumentierten Ubuntu-26.04-/Postfix-/Dovecot-2.4-Stand abgestimmt und ersetzt keine bestehende Serverinstallation.

```sh
sudo python3 deploy/io-website.py install --ref v0.1.2
# nach erfolgreicher Installation:
sudo io-website update
sudo io-website status
sudo io-website rollback
```

DNS-Einträge werden bei Bedarf ausgegeben und müssen bei STRATO gesetzt werden. Das Script ändert DNS nicht automatisch. Die Einrichtung erfordert einen administrativen Terminalzugang auf dem Zielserver.

## Seiten und Pflege

HTML in `src/`, lokale Assets in `src/website-assets/`; SVG-Logo `io-logo.svg` und Bildzeichen `io-mark.svg`.

Startseite, Leistungen, Unternehmen, Entwicklung → Rail Software, KI-Musik, Kontakt, Impressum und Datenschutz. Die öffentliche Demo-/Download-Seite ist ausschließlich eine Statusseite; persönliche Konten folgen später. Keine öffentlichen TF-/Verwaltungslinks, keine vertraulichen Inhalte in statischen Dateien.

```sh
python3 scripts/build.py
python3 scripts/check_static.py
python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s deploy/tests -v
node --check src/website-assets/site.js
```

`dist/` enthält den vollständigen statischen Export. GitHub Actions stellt ihn als Artefakt bereit. Nur der getrennte Formularversand nutzt einen eigenen unprivilegierten Python-Dienst. Kontaktadresse und fester Empfänger: `info@io-goerlitz.eu`, ohne Gmail-Weiterleitung für dieses Postfach. In der privaten Sites-Vorschau bleibt der Formularversand deaktiviert.

[Server-Veröffentlichung](docs/SERVER-VEROEFFENTLICHUNG.md) · [Kontaktbetrieb](docs/KONTAKTFORMULAR.md) · [Redaktion](docs/REDAKTION.md) · [Versionsänderungen](CHANGELOG.md)

Sites speichert eine eigene Quellkopie für die private Vorschau. Keine automatische Synchronisation aus GitHub oder automatische Server-Veröffentlichung durch GitHub Actions. Die Strato-Website wird erst durch den Installationslauf auf dem Zielserver umgeschaltet.
