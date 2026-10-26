# Uptime Monitor

[English](README.md) | [Русский](README.ru.md) | **Deutsch**

> Die englische Version ([README.md](README.md)) ist massgebend. Die deutsche kann etwas hinterherhinken.

Asynchroner Dienst zur Verfügbarkeitsüberwachung von Websites, gebaut mit
**FastAPI** und **asyncio**.

Du registrierst Websites über eine REST-API. Ein Hintergrund-Scheduler prüft sie
danach alle nebenläufig in einem festen Intervall (über `httpx`) und speichert den
Verlauf jeder Prüfung — Statuscode, Antwortzeit und ob die Website erreichbar war.

> Ein MVP rund um echtes async I/O: nebenläufige Netzwerkprüfungen mit begrenzter
> Parallelität, eine Hintergrundaufgabe im Lifespan der Anwendung, eine geschichtete
> Architektur und Dependency Injection.

---

## Technologie-Stack

| Bereich | Wahl |
| --- | --- |
| Sprache | Python 3.14 |
| Web-Framework | FastAPI + Uvicorn (ASGI) |
| API-Doku | Swagger UI / OpenAPI (automatisch generiert) |
| HTTP-Client | httpx (async) |
| Datenbank | SQLite über SQLAlchemy 2.0 (async) + aiosqlite |
| Validierung / Einstellungen | Pydantic v2, pydantic-settings |
| Tests | pytest, pytest-asyncio |
| Paketverwaltung | uv |
| Containerisierung | Docker |

---

## Projektstruktur

```
app/
  main.py            # FastAPI-App + Lifespan (startet den Hintergrund-Scheduler)
  config.py          # Einstellungen (per Umgebungsvariablen überschreibbar)
  database.py        # Async-Engine, Session-Factory, Fail-fast-DB-Prüfung
  models.py          # SQLAlchemy-Modelle: Site, CheckResult
  schemas.py         # Pydantic-Schemas (API-Ein-/Ausgabe)
  crud.py            # Datenbankoperationen (kennt kein HTTP)
  installation.py    # Einmalige Datenbankeinrichtung (Tabellen anlegen)
  routers/
    sites.py         # /sites-Endpunkte
  monitor/
    checker.py       # check_site(): prüft EINE Website (reines Netzwerk, keine DB)
    scheduler.py     # run_monitor(): Hintergrundschleife, nebenläufige Prüfungen
tests/
  test_database.py   # Tests für die Fail-fast-DB-Prüfung
```

Die Schichten sind getrennt: `checker` kennt das Netzwerk, aber nicht die Datenbank;
`crud` kennt die Datenbank, aber nicht HTTP; und `scheduler` ist der einzige Ort, an
dem sie zusammentreffen.

---

## Einrichtung

Benötigt [uv](https://docs.astral.sh/uv/). Abhängigkeiten installieren:

```bash
uv sync
```

Das erstellt eine lokale virtuelle Umgebung (`.venv`) und installiert alles aus
`uv.lock`.

> **Führe alle Befehle aus dem Projektstammverzeichnis aus.** Der Datenbankpfad ist
> relativ; ein Start aus einem anderen Verzeichnis lässt die Anwendung die Datenbank
> am falschen Ort suchen — und sie verweigert den Start, statt eine leere anzulegen.

---

## Datenbank

Die Anwendung erstellt die Datenbank nie von selbst (fail-fast: fehlt die Datenbank,
verweigert sie den Start, statt still eine leere anzulegen). Erstelle sie einmalig
mit dem Installationsbefehl:

```bash
uv run python -m app.installation
```

Alle Tabellen löschen und neu anlegen (**löscht alle Daten**):

```bash
uv run python -m app.installation --force
```

---

## Server starten

```bash
uv run uvicorn app.main:app --reload
```

Danach die interaktive API-Doku (Swagger UI) öffnen:

```
http://127.0.0.1:8000/docs
```

Beim Start beginnt der Hintergrund-Scheduler, aktive Websites zu prüfen.
Zusammenfassungen pro Runde werden in der Konsole protokolliert, zum Beispiel:

```
Round done: 6 checked, 4 down, took 5.02s
```

---

## Mit Docker ausführen

Image bauen:

```bash
docker build -t uptime-monitor .
```

Die Datenbank einmalig anlegen — in einem gemounteten Volume, damit sie Neustarts übersteht:

```bash
docker run --rm -v ./data:/app/data uptime-monitor python -m app.installation
```

Den Dienst starten (Port 8000 und das Volume `./data` werden durchgereicht):

```bash
docker run -d -p 8000:8000 -v ./data:/app/data --restart unless-stopped --name uptime uptime-monitor
```

Öffne http://127.0.0.1:8000/docs. Logs mit `docker logs -f uptime`, stoppen mit
`docker stop uptime`. Die Datenbank liegt im Volume `./data` (über `DATABASE_URL`) und
übersteht so Neustart und Entfernen des Containers. Ein Named Volume
(`-v uptime-db:/app/data`) funktioniert genauso gut; der Bind-Mount ist hier
gewählt, damit die Datenbankdatei vom Host aus sichtbar bleibt.

### Unter Windows mit WSL2

Geprüft mit Docker Engine innerhalb einer WSL2-Distribution, ohne Docker Desktop:
Build, Dienst und das Schreiben des Schedulers in SQLite über den Bind-Mount
funktionieren, und der veröffentlichte Port ist aus Windows unter
`127.0.0.1:8000` erreichbar.

Eine Besonderheit: WSL2 fährt seine virtuelle Maschine herunter, sobald sie
niemand mehr nutzt, und der Container stoppt mit ihr. `--restart unless-stopped`
startet den Container wieder, sobald Distribution und `docker.service` erneut
laufen, es gehen also keine Daten verloren. Für den Dauerbetrieb lass eine
WSL-Sitzung offen.

---

## Konfiguration

Alle Einstellungen haben Standardwerte und lassen sich über Umgebungsvariablen
überschreiben:

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `CHECK_INTERVAL_SECONDS` | `30` | Pause zwischen den Prüfrunden |
| `REQUEST_TIMEOUT_SECONDS` | `5` | httpx-Timeout für eine Anfrage (pro Phase angewandt) |
| `MAX_CONCURRENT_CHECKS` | `20` | Maximale Anzahl gleichzeitiger Prüfungen |
| `CHECK_DEADLINE_SECONDS` | `15` | Harte Frist für eine Prüfung — Absicherung über dem httpx-Timeout |
| `ROUND_TIMEOUT_SECONDS` | `120` | Harte Frist für eine ganze Runde; bei Ablauf wird sie abgebrochen und der Scheduler macht weiter |
| `DATABASE_URL` | `sqlite+aiosqlite:///./monitor.db` | Verbindungszeichenfolge zur Datenbank |

Beispiel (Windows PowerShell):

```powershell
$env:CHECK_INTERVAL_SECONDS = 10
uv run uvicorn app.main:app
```

---

## API

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `POST` | `/sites` | Website hinzufügen: `{ "url": "...", "name": "..." }` |
| `GET` | `/sites` | Alle Websites auflisten |
| `GET` | `/sites/{id}` | Eine Website abrufen |
| `DELETE` | `/sites/{id}` | Eine Website samt Verlauf löschen |

Eine Website gilt als **erreichbar (up)**, wenn sie geantwortet hat und der Statuscode
unter 500 liegt. Ein `4xx` zählt weiterhin als erreichbar (der Server ist gesund, das
Problem liegt an der Anfrage); nur Timeouts, Verbindungsfehler und `5xx` gelten als
nicht erreichbar (down).

---

## Eine einzelne Prüfung ausprobieren

`checker.py` ist ein Bibliotheksmodul (kein Kommandozeilen-Einstiegspunkt). Um eine
Prüfung interaktiv auszuprobieren, nutze die Python-REPL:

```bash
uv run python
```

```python
import asyncio, httpx
from app.monitor.checker import check_site

async def try_url(url):
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        return await check_site(client, url)

asyncio.run(try_url("https://example.com"))
# CheckOutcome(is_up=True, status_code=200, response_time_ms=120.4, error=None)

asyncio.run(try_url("https://httpbin.org/status/500"))
# CheckOutcome(is_up=False, status_code=500, response_time_ms=310.0, error='http_500')
```

---

## Tests

```bash
uv run pytest
```

---

## Roadmap

- `GET /sites/{id}/checks` — jüngster Prüfverlauf
- `GET /sites/{id}/stats` — Verfügbarkeit in % und durchschnittliche Antwortzeit über einen Zeitraum
- Unit-Tests für `check_site` mit `httpx.MockTransport`
