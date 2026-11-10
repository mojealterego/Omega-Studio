# API Reference — OMEGA Studio Ultimate v1

## Uwierzytelnianie

Główny serwer lokalny: każdy `/api/*` wymaga `X-OMEGA-Token: <session-token>` uzyskanego z lokalnej strony `/ultimate`; dodatkowo odrzucane są obce Origin. Token nie powinien być wysyłany poza localhost. Zdalny `remote8080` jest odrębnym serwerem, z Basic auth oraz TLS dla bind spoza loopback.

## Endpoints Workbench

| Metoda | Ścieżka | Parametry / wynik |
|---|---|---|
| GET | `/ultimate` | Premium HTML PL |
| GET | `/api/ultimate/status` | `features`, `runtime_executables_on_host`, `scope` |
| GET | `/api/ultimate/repositories` | `organization` (domyślnie github), `pages` (domyślnie 20); pobiera publiczne repozytoria i zapisuje SQLite |
| GET | `/api/ultimate/search` | `q` (max 256), `limit` (1..1000); `items`, `total` |
| POST | `/api/ultimate/assets` | JSON `{kind: svg|png|wav|gltf|mp4, text: string}`; binarne media |
| POST | `/api/ultimate/analyze` | JSON `{source,mode:leak|duo}`; 4 statyczne analizatory AST, findings, sha256, verified |
| POST | `/api/ultimate/nocode` | JSON `{description: string}`; `html`, `type`, `requires_cloud_ai` |
| POST | `/api/ultimate/simulate` | `seed`, `jobs`; 10 niezmienników, wynik digital twin |

### Przykład statusu

```bash
curl -H "X-OMEGA-Token: $OMEGA_TOKEN" http://127.0.0.1:8080/api/ultimate/status
```

Przykład odpowiedzi: `{"features":{"repo_crawler":"ready","streaming":"ready","assets":"procedural","swarm":"bounded","nocode":"template"},"runtime_executables_on_host":{...},"scope":"host-process-not-android-apk"}`.

### Crawler

`GitHubOrgCrawler.crawl(organization, pages=20, per_page=100)` zwraca listę rekordów `full_name`, `description`, `language`, `license`, `default_branch`, `html_url`, `size_kb`. Repozytorium nie jest klonowane przez sam indeks. `download_snapshot(owner,repo,revision,destination,max_archive_bytes=...)` wymaga 40-znakowego SHA i zwraca sumę SHA-256 pobranego ZIP oraz liczbę wyodrębnionych plików.

### Multi-cloud Python API

- `MultiCloudHub.gitlab_projects(page=1,per_page=100,token=None)` — lista projektów z GitLab.
- `MultiCloudHub.hf_models(limit=100,token=None)` — lista modeli HF.
- `MultiCloudHub.drive_files(token,page_token=None,page_size=100)` — lista plików Google Drive, wymaga OAuth.

Konektory są tylko do odczytu. Nie publikują repozytoriów ani nie uruchamiają ich kodu.

## Zdalny serwer `remote8080`

| Metoda | Ścieżka | Kontrakt |
|---|---|---|
| GET | `/` | Strona statusowa premium |
| GET | `/api/files` | Lista plików w katalogu głównym workspace (maks. 1000) |
| GET | `/api/read?path=...` | UTF-8 do 1 MiB, `content`, `sha256` |
| PUT | `/api/write` | `{path,content,expected_sha256}`; 409 dla konfliktu, 403 traversal |
| WS | `/ws` | Basic Authorization przy handshake, `hello`, `ping`→`pong` |

`expected_sha256` jest wymagane przy modyfikacji istniejącego pliku, aby wykryć nadpisanie równoległej zmiany.

## CLI

`omega-ultimate {zip-pack|zip-extract|rar-pack|rar-extract|copy|asset|crawl|search|seal|simulate|serve}`; każdy błąd walidacji kończy się kodem 2 i komunikatem na stderr.

## Istniejące API

`/api/providers`, `/api/providers/chat`, `/api/models`, `/api/models/hf/download`, `/api/runs`, `/api/compile`, `/api/secrets`, `/api/omega/simulation`, `/api/omega/telemetry` — ich implementacje znajdują się w `backend/omega_actions/api.py`. Zewnętrzne modele wymagają osobnej zgody na koszt, a hasła skarbca nie są zwracane do UI.

## Format błędów

HTTP 401 brak tokenu, 403 niedozwolony Origin/ścieżka, 409 konflikt pliku, 413 za duży plik, 415 binarny plik w edytorze tekstowym, 422 walidacja wejścia, 503 brak konfiguracji usług. Brak automatycznego retry po 401/403.

## Biblioteka Open Source

`GET /api/ultimate/upstreams` — lista źródeł, commit SHA, licencja, rola. `POST /api/ultimate/upstreams/sync` — JSON `{ "name": "termux-app", "confirm_network": true }`; wymaga nagłówka `X-OMEGA-Token`, pobiera jedynie przypięte źródło do prywatnego katalogu i zapisuje pochodzenie. Bez zgody HTTP 403, błędy walidacji HTTP 422. API nie wykonuje pobranego kodu.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
