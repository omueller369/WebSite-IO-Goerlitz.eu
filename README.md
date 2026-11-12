# Rail Software Website / IO-Software-Görlitz

Eigenständige statische Präsentation mit separatem Kontakt-Maildienst.
Pflegebasis: `omueller369/WebSite-IO-Goerlitz.eu`; unabhängig von `omueller369/RailSoftware`.
Kein Submodul, keine Backend-Kopplung, keine gemeinsamen Builds.

## Seiten

- `/`: Startseite
- `/leistungen/`: Beratung, Auftragsentwicklung, Leasing, Wartung und Betreuung
- `/unternehmen/`: privates Projekt von Oliver Müller, Görlitz
- `/entwicklung/`: Produktübersicht
- `/entwicklung/rail-software/`: öffentliche Produktvorstellung, Status „in Entwicklung“
- `/entwicklung/rail-software/demo-download/`: öffentliche Statusseite ohne geschützte Inhalte; Konten, Demo und Downloads folgen später
- `/ki-musik/`: persönliche Songs, Unternehmensmusik, Intros und Hintergrundmusik
- `/kontakt/`, `/impressum/`, `/datenschutz/`

TF-Portal und Verwaltung sind auf keiner öffentlichen Seite verlinkt. Ihre bestehenden Adressen und ihre vorhandene Authentifizierung bleiben unberührt. Eine zusätzliche serverseitige Zugangssperre und persönlich angelegte Demo-Konten sind noch nicht umgesetzt. Niemals vertrauliche Inhalte in `src/` oder `dist/` ablegen: alle statischen Dateien sind abrufbar.

## Pflege, Logo und Export

HTML in `src/`, lokale Assets in `src/website-assets/`. SVG-Logo: `io-logo.svg` (Wortmarke) und `io-mark.svg` (Bildzeichen). Gestaltung: Petrol und Hellgrün, keine externen Fonts, Tracker oder Einbettungen.

```sh
python3 scripts/build.py
python3 scripts/check_static.py
python3 -m unittest discover -s server/tests -v
node --check src/website-assets/site.js
```

`dist/` ist der vollständige statische Export ohne Node-/Python-Laufzeit auf dem Webserver. GitHub Actions stellt diesen Export als Artefakt `rail-software-website-static` bereit; keine automatische Server-Veröffentlichung.

Das Kontaktformular braucht für tatsächlichen Versand den unabhängig bereitgestellten WSGI-Maildienst in `server/`. In der privaten Sites-Vorschau und bei fehlender SMTP-Konfiguration bleibt der Versand deaktiviert. Telefon und E-Mail funktionieren als alternative Kontaktwege. Keine Daten werden von der Vorschau an den Produktivserver gesendet.

## Veröffentlichung

[Server-Anleitung](docs/SERVER-VEROEFFENTLICHUNG.md), [Apache-Website-Fragment](docs/apache-website.conf.example), [Kontaktbetrieb](docs/KONTAKTFORMULAR.md), [Redaktions- und Freigabehinweise](docs/REDAKTION.md).

Sites verwaltet eine getrennte Quellkopie für die private Vorschau. Änderungen im GitHub-Repository müssen für eine neue Sites-Version übernommen werden; keine automatische Synchronisation eingerichtet. Die Strato-Zieldomain wurde nicht umgestellt.
