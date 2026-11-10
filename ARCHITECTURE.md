# Architektura OMEGA Studio Ultimate

## Topologia procesów

```text
┌─────────────────────────── Android source ───────────────────────────┐
│ Java MainActivity / NativeBridge / SecureVault / CodeServerManager   │
│ AppBuilder UI, Editor, Terminal, GGUF / HF, API Providers             │
│ RuntimeAssetsInstaller ── ELF/ARM64 + prefix + SHA256 release gate   │
└───────────────────────────────────────────────────────────────────────┘
                           [niezależny wariant desktop/host]
┌────────────────────────────── Host / Python ─────────────────────────┐
│ Uvicorn FastAPI 127.0.0.1:8080                                        │
│ ├─ /ultimate  Premium Workbench (HTML/CSS/JS, PL)                    │
│ ├─ /api/ultimate  Catalog / Search / NoCode / Assets / Simulation     │
│ ├─ /api  Local CI/CD / Secrets / GGUF / Providers / GitHub            │
│ └─ /  Workflow Studio                                                 │
│ Ultimate modules: crawler, cloud, streamer, archives, swarm, seal,    │
│                   assets, simulation, remote8080                       │
│ Storage: SQLite, local workspace, content-addressed artifacts        │
│ Security: Argon2id + AES-256-GCM + HMAC-SHA3-256, bearer token        │
└───────────────────────────────────────────────────────────────────────┘
```

## Rozdzielenie odpowiedzialności

| Warstwa | Implementacja | Kontrakt |
|---|---|---|
| UI | `static/ultimate.{html,css,js}` | JSON API z `X-OMEGA-Token`; iframe `sandbox` |
| Repo crawler | `ultimate/crawler.py` | GitHub REST `GET /orgs/{org}/repos`, `page=1..N`, `per_page≤100` |
| Multi-cloud | `ultimate/cloud.py` | GitLab `/api/v4/projects`, HF `/api/models`, Google Drive `/drive/v3/files` |
| Index | `RepositoryIndex` | SQLite UPSERT po `full_name`, lokalny search |
| Streamer | `WindowedReader` | Okna `mmap`, SHA-256, bounded memory |
| Archiwa | `ultimate/archives.py` | Deterministyczny ZIP, weryfikacja CRC, kwoty, RAR adapter |
| Rój | `ultimate/swarm.py` | Bounded worker pool, Chat Duo generator/verifier, graf dyfuzji |
| Pieczęć | `ultimate/seal.py` | Python AST, `χ`, `β1`, HMAC-SHA3-256 |
| Assety | `ultimate/assets.py` | SVG, PNG, WAV, MP4/FFmpeg, glTF 2.0 animation |
| Local CI | `omega_actions/engine.py` | DAG, izolacja workspace, timeout, redakcja sekretów |
| GGUF | `omega_actions/model_studio.py` | GGUF v2/v3 header, limity metadanych, HF download |
| Serwer zdalny | `ultimate/remote8080.py` | Basic auth, TLS dla interfejsów nie-loopback, atomic write |

## Przepływ indeksowania

1. Użytkownik wskazuje organizację, liczbę stron i uruchamia crawler.
2. Crawler odpytuje **wyłącznie** `api.github.com`, waliduje każdą nazwę repozytorium, stosuje limity i sygnalizuje rate-limit.
3. Metadane zapisują się do SQLite. Brak automatycznego klonowania.
4. Świadomie wybrany snapshot pobiera się z `codeload.github.com` dla wskazanego SHA commita; archiwum przechodzi kontrolę traversal, symlink, quota i CRC.
5. Kod obcy pozostaje w odrębnym workspace i nie jest automatycznie wykonywany.

## Niezmienniki i granice

- Crawler nie używa adresów URL przekazanych przez rekordy GitHub do żądań sieciowych.
- Rój ma limit aktywnych i oczekujących zadań, a pętla Duo limit prób.
- Archiwum nie może wyjść poza katalog docelowy ani utworzyć symlinków.
- Zmiany plików zdalnych wymagają zgodnego SHA-256 wersji początkowej.
- Remote gateway nie otwiera się na publicznej sieci bez TLS.
- Symulacja nie może podwyższyć statusu binarnego Android runtime.

## Upstream Supply Chain

Moduł `backend/omega_actions/ultimate/upstream_sources.py` waliduje 12 źródeł z `config/upstream_sources.lock.json`, wykonuje wyłącznie opt-in checkout po SHA i przechowuje provenance. `GET /api/ultimate/upstreams` publikuje metadane, `POST /api/ultimate/upstreams/sync` wymaga autoryzacji i świadomej zgody. Środowisko wykonawcze pozostaje odseparowane od pobranych źródeł.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
