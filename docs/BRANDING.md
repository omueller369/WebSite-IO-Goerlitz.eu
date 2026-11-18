# IO-Software-Görlitz – Erscheinungsbild 0.3.0

## Entwurf

Neues IO-Monogramm: vorwärts geneigte Buchstaben, weinrotes I und dunkelblaues O, eine verbindende Leiterbahn mit Kontaktpunkten und zwei parallele Grundlinien. Leiterbahn und klare Geometrie stellen Softwareentwicklung in den Vordergrund; die Grundlinien und Farbigkeit schaffen die Verbindung zu Rail Software.

Der Entwurf wurde mit dem Bildgenerator auf Basis dieses Briefings erstellt. Das bestehende RS-Logo diente als Referenz für Farbfamilie und geometrischen Charakter, nicht als zu überschreibende Bilddatei.

## Farbfamilie

| Funktion | Farbe |
| --- | --- |
| Dunkelblau, Schrift und dunkle Flächen | `#002548` |
| Weinrot, Akzente und primäre Aktionen | `#8C001F` |
| Aktive/dunklere Weinrot-Abstufung | `#740019` |
| Sekundärtext | `#50667F` |
| Seitenhintergrund | `#F7F9FC` |
| Helle Kartenflächen | `#EDF2F8` |

Die Referenzfarben wurden aus den häufigen dunkelblauen und weinroten Farbtönen des vorhandenen Rail-Software-Logos abgeleitet. Das rasterbasierte Monogramm enthält leichte Abstufungen. Primäre Buttons verwenden weiße Schrift auf Weinrot; dunkle Abschlussbereiche verwenden weiße Flächen mit weinroter Schrift für die Aktion.

## Dateien

- `src/website-assets/io-mark.png`: transparentes generiertes Original; unverändert kopiert.
- `src/website-assets/io-mark.svg`: SVG-Rahmen mit eingebettetem PNG und passendem ViewBox-Ausschnitt für Kopfbereich, Hero und Favicon. Kein externer Bildabruf erforderlich.
- `src/website-assets/io-logo.svg`: Wortmarke mit eingebettetem PNG-Zeichen und SVG-Schriftzug „IO-Software-Görlitz / Softwareentwicklung“. Dies ist eine SVG-Komposition mit Raster-Bildzeichen, keine vollständig vektorisierte Bildmarke.
- `src/website-assets/rail-software-logo.png`: unverändertes Produktlogo aus `omueller369/RailSoftware`, Tag `android-test-43`, Datei `backend/lokzeitleiste/static/rail-software-logo.png`. Die Wahl und Bedeutung sind dort in `docs/BRANDING.md` dokumentiert.

Das zweifarbige Logo auf hellem Grund verwenden. Auf dunklen Flächen einen hellen Hintergrund vorsehen, damit das dunkelblaue O erkennbar bleibt. Die Website setzt dies in allen eingebauten Anwendungen um.

## Website und Serverbereich

Kopfbereich, Hero, Unternehmensvorstellung, Rail-Produktdarstellung, Buttons, Formulare, Fokusmarkierungen, Karten und Footer verwenden die neue Farbwelt. Download und Kundenverwaltung laden dasselbe Stylesheet und zeigen dasselbe Logo. Versionsparameter `v=0.3.0` sorgen dafür, dass die neuen Logos und CSS-Dateien nach dem Update neu geladen werden.

Eine Änderung an den RailSoftware-Anwendungsdateien ist für dieses Erscheinungsbild nicht nötig. Das eigene Website-Repository bleibt die Pflegebasis. Update auf dem eingerichteten Server: `sudo io-website update --ref v0.3.0`.
