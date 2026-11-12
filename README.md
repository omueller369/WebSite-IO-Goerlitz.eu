# Rail Software Website

Eigenständige statische Website. GitHub: `omueller369/WebSite-IO-Goerlitz.eu`.
Unabhängig von `omueller369/RailSoftware`: keine Submodule, keine Backend-Dateien, keine gemeinsamen Builds.

## Pflege und Export

Inhalte: `src/index.html`; Gestaltung: `src/website-assets/site.css`.

```sh
python3 scripts/build.py
```

`dist/` enthält die vollständigen Veröffentlichungsdateien, ohne Laufzeit, Datenbank, externe Fonts, JavaScript oder Paketabhängigkeiten. Der Export kann bei jedem statischen Webserver betrieben werden. Alle Portal-Links zeigen absichtlich auf den bestehenden HTTPS-Server, auch in der Sites-Vorschau.

GitHub Actions exportiert bei Push und manuellem Start die Veröffentlichungsdateien als herunterladbares Artefakt `rail-software-website-static`. Es findet keine automatische Server-Veröffentlichung statt.

## Getrennte Veröffentlichung

Siehe [Server-Anleitung](docs/SERVER-VEROEFFENTLICHUNG.md) und [Apache-Vorlage](docs/apache-website.conf.example).
Sites verwaltet eine eigene Quellkopie für seine Vorschau; dieses GitHub-Repository bleibt die unabhängige Pflegebasis. Änderungen aus GitHub müssen für eine aktualisierte Sites-Veröffentlichung übernommen werden; es gibt keine eingerichtete automatische Synchronisation.

## Routing-Vertrag

Die neue Website belegt ausschließlich `/` (sowie `/index.html`) und `/website-assets/`. Alle anderen Pfade werden weiterhin von der vorhandenen Software bedient, insbesondere `/tf`, `/admin`, APIs, Anmelde-, Installations- und PWA-Dateien. Kein SPA-Fallback und keine Änderung am DNS oder Backend.

Die Server-Anleitung ist vorbereitet; die Zieldomain wurde nicht umgestellt. Rechtliche Pflichtangaben müssen vor öffentlicher Freischaltung anhand der tatsächlichen Betreiberangaben ergänzt werden.
