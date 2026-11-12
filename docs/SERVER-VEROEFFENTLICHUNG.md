# Getrennte Server-Veröffentlichung

Ziel: https://ctl-software.io-goerlitz.eu/
Website-Quelle: https://github.com/omueller369/WebSite-IO-Goerlitz.eu

Diese Anleitung verändert keine Software und installiert kein Backend. Die aktuelle Server-Konfiguration und Zugangsdaten liegen hier nicht vor. Apache ist anhand der RailSoftware-Dokumentation die Arbeitsannahme; die produktive Konfiguration ist vor Anwendung abzugleichen. Es wurde kein Serverzugriff und keine DNS-Änderung vorgenommen.

## 1. Bestand sichern und prüfen

Auf dem Server den zuständigen HTTPS-VirtualHost mit `sudo apache2ctl -S` bestimmen. Seine Konfiguration samt eingebundenen Dateien sichern. Alle bestehenden ProxyPass-, Alias-, Rewrite-, Location- und Service-Worker-Regeln aufnehmen. Backend-Ziel, TLS, Authentifizierung, Header und Timeouts beibehalten. Bei Nginx oder einer anderen Architektur diese Apache-Vorlage nicht verwenden.

Vorher-Nachher-Prüfliste aus den tatsächlich eingesetzten Software-Routen erstellen: `/tf`, `/tf/`, `/tf/install`, `/admin`, `/admin/`, `/admin/install`, sämtliche API-Routen (auch außerhalb von `/api`), Downloads, `/locales/`, `/auth-session.js`, `/i18n.js`, Manifest- und Service-Worker-Dateien. Die derzeitige Startseite bindet diese drei JavaScript-Pfade und `/admin/portal.css` ein. Backend-Routen und Zugriffsprotokolle bilden die vollständige Liste, nicht diese Beispiele. Keine API- oder Login-Antwort im öffentlichen Repository speichern.

Status, Weiterleitungsziel und Content-Type der bestehenden Routen protokollieren. Authentifizierung kann erwartete 401/403 oder Login-Weiterleitungen liefern. Für funktionale Kontrollen ein Testkonto verwenden; keine verändernden API-Aufrufe nur zum Testen ausführen. Service-Worker-Caches auf beiden Portalen prüfen: ein Worker mit Root-Scope darf die neue Startseite nicht weiter durch eine gecachte alte Seite ersetzen.

## 2. Separaten Export erstellen

Auf dem Pflege-Rechner das neue Repository klonen, einen geprüften Commit auswählen und exportieren:

```sh
git clone https://github.com/omueller369/WebSite-IO-Goerlitz.eu.git
cd WebSite-IO-Goerlitz.eu
python3 scripts/build.py
```

Alternativ in GitHub Actions das Artefakt `rail-software-website-static` des gewünschten Commits herunterladen. Nur den Inhalt von `dist/` veröffentlichen, nicht Repository, `.openai`, Dokumentation oder Workflow. Keinen Kopierbefehl mit `--delete` auf ein vorhandenes Software-Verzeichnis anwenden.

## 3. Eigenes Release-Verzeichnis übertragen

Auf dem Server `/var/www/rail-website/releases/` als eigenes Website-Verzeichnis anlegen. Ein eindeutiges Release-Verzeichnis verwenden, z. B. `20261112-<commit>`. Die Dateien über den üblichen administrativen Übertragungsweg dorthin kopieren. Ergebnis:

```text
/var/www/rail-website/releases/<release>/index.html
/var/www/rail-website/releases/<release>/website-assets/site.css
```

Webserver-Leserechte auf Dateien und Durchgangsrechte auf Elternverzeichnisse setzen; kein Schreibrecht für den Webserver nötig. `current` muss ein Symlink sein und darf nicht als bestehendes Verzeichnis überschrieben werden.

```sh
cd /var/www/rail-website
ln -s releases/<release> current.next
mv -Tf current.next current
```

`<release>` vorher durch den echten Ordnernamen ersetzen. Bei Folge-Releases das vorherige Linkziel mit `readlink current` für Rollback festhalten.

## 4. Nur die expliziten Website-Pfade zuordnen

Die Datei `apache-website.conf.example` ist ein Einfügefragment für den bestehenden HTTPS-VirtualHost. Die Proxy-Ausnahmen müssen VOR jeder allgemeinen ProxyPass-Regel stehen. Alle bisherigen Backend-Zuordnungen danach unverändert lassen. Das vorhandene `/website-assets/` muss vorab unbenutzt sein; andernfalls einen neuen Namen sowohl in HTML als auch in der Konfiguration wählen.

Nur `/`, `/index.html`, die explizit im Apache-Fragment aufgelisteten Präsentationsseiten (mit und ohne abschließenden Slash) und `/website-assets/` gehen zum statischen Export. Die Kontakt-Route `/website-contact` wird ausschließlich über das separate Kontaktfragment zugeordnet. Jeder andere Pfad folgt weiter den bisherigen Software-Regeln. Es gibt keinen `index.html`-Fallback für unbekannte Routen. Kein DNS-Umschalten auf Sites: Das würde ohne zusätzliches Routing das vorhandene Backend umgehen. Die Sites-Adresse ist eine getrennte Vorschau und nicht der Ersatz für den Software-Host.

Apache-Regeln aus verschiedenen Kontexten können sich überlagern. Vorhandene Rewrite-/Location-Regeln, die `/` oder Assets abfangen, mit dem tatsächlichen VirtualHost abstimmen. Bei fehlender Klarheit zuerst auf einer Kopie des VirtualHosts testen.

```sh
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Reload nur bei erfolgreichem Konfigurationstest.

## 5. Abnahme und Rückweg

- `/` und `/index.html` zeigen die neue Seite; `/website-assets/site.css` liefert CSS.
- Alle zuvor aufgenommenen Routen behalten Status, Weiterleitung, Authentifizierung und Content-Type. Keine API liefert das HTML der Startseite.
- TF-/Admin-Anmeldung, Installation, PWA und verwendete Software-Abläufe mit Testkonto prüfen. Desktop und Mobilgerät kontrollieren.
- Browser mit bestehendem Portal-Service-Worker und frisches Browserprofil prüfen.
- Bestehende unbekannte Pfade behalten ihr bisheriges Verhalten.

Bei Routingfehlern das eingefügte Fragment entfernen bzw. die gesicherte VirtualHost-Konfiguration wiederherstellen, `configtest` ausführen und Apache neu laden. Bei reinem Inhaltsfehler `current` mit derselben Symlink-Methode auf das vorherige Release zurücksetzen. Alte Releases für den Rückweg behalten. Backend, Datenbank und `RailSoftware` werden bei Website-Releases nicht neu gestartet oder geändert.

## Pflege

Änderungen nur in diesem Website-Repository vornehmen; Export prüfen, neues Release kopieren und Symlink umschalten. Keine automatische Server-Veröffentlichung und keine Repository-Verknüpfung mit RailSoftware. Betreiberangaben, Impressum und Datenschutzhinweise vor öffentlicher Freischaltung fachlich ergänzen. Die neue Seite selbst verwendet keine Cookies, Tracker oder extern geladenen Ressourcen; die verlinkten Portale haben eigene Datenverarbeitung.

## Ergänzung: Mehrseitige Präsentation und Kontakt

Die Website enthält jetzt Leistungen, Unternehmen, Entwicklung/Rail Software, KI-Musik, Kontakt, Impressum und Datenschutz. Sämtliche neuen Seitenpfade müssen vor der Übernahme auf Konflikte geprüft werden. Das Apache-Fragment enthält eine geschlossene Pfadliste, keinen Präfix-Catch-all für `/entwicklung`. Auch unbekannte Unterpfade bleiben beim bisherigen Backend. `/tf`, `/admin`, `/api` und alle sonstigen vorhandenen Software-Pfade werden nicht überschrieben.

Der optionale Formularversand wird getrennt nach [KONTAKTFORMULAR.md](KONTAKTFORMULAR.md) eingerichtet. Für die Freigabe rechtlicher Texte [REDAKTION.md](REDAKTION.md) abarbeiten. Die bestehende Portal-Authentifizierung bleibt erhalten; eine neue gemeinsame Zugangssperre ist noch nicht umgesetzt. Öffentlich sind keine Portal-Links vorhanden. Die Demo-/Download-Seite ist nur eine öffentliche Statusseite ohne Demo, Dateien oder Login-Simulation.
