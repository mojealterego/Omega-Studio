# Testing & Validation — wyniki rzeczywistych uruchomień

## Dowody hostowe

| Bramka | Wynik | Artefakt |
|---|---|---|
| Python (stary backend + nowe moduły) | **197 PASS, 4 podtesty PASS, 0 FAIL** | `validation/ultimate/full_py.log` |
| Node.js (UI/AppBuilder) | **15 PASS, 0 FAIL** | `validation/ultimate/full_js.log` |
| Lokalny CI/CD E2E | **PASS**, dwa rzeczywiste joby native | `validation/ultimate/real_ci.log` |
| Deterministic Engineering Simulation | **10/10 niezmienników PASS** | `validation/ultimate/simulation.json` |
| Chromium desktop/mobile | **PASS, 0 page errors** | `validation/ultimate/browser_result.json` i PNG |
| Rzeczywiste lokalne HTTP | **PASS** (port 18080; 8080 zajęty przez inny proces w tym środowisku) | `validation/ultimate/browser_final.log` |
| ZIP/CRC/SHA-256 | **PASS** | `MANIFEST_SHA256.txt`, zewnętrzny raport `OMEGA_STUDIO_ULTIMATE_PRODUCTION_PACKAGE_v1.0.0.validation.json` |
| Kompilacja źródeł Android przeciw stubom | Host-only, wynik w `android_sources.log` | `validation/ultimate/android_sources.log` |
| APK z kompletem binariów ARM64 | **Nie zbudowano** | `PRODUCTION_READINESS_REPORT.md` |
| Test na fizycznym Androidzie | **Nie przeprowadzono** | `PRODUCTION_READINESS_REPORT.md` |

W teście Python wystąpiło ostrzeżenie `zipfile` dotyczące **celowo zduplikowanego wpisu** w negatywnym teście walidatora bootstrap. Nie oznacza to pominięcia testu.

## Nowe kontrole synchronizacji

- `tests/ultimate/test_remote_ide.py`: 3 testy uwierzytelnionego edytora i API drzewa katalogów.
- `tests/test_android_apk_release_gate.py`: 3 testy negatywne podglądowego i nieprawidłowego APK.
- `tools/test_remote_ide_browser.py`: rzeczywiste interakcje Chromium na HTML, transport `fetch` mockowany ze względu na izolację sieciową przeglądarki.
- `tools/verify_android_apk_release.py`: rzeczywisty walidator zasobów ARM64 i podpisu APK; odrzuca niekompletne archiwa.

## Zakres testów Ultimate

- `tests/ultimate/test_streaming_archives.py`: mmap, 5 GiB sparse, SHA-256, sendfile, deterministyczny ZIP, Zip Slip, symlink, quota, błędny RAR.
- `test_crawler_cloud.py`: 20 stron GitHub, walidacja, rate-limit, snapshot pinned SHA, GitLab/HF/Drive przez MockTransport.
- `test_swarm_seal_assets.py`: dyfuzja grafowa, rój, Chat Duo, AST seal, PNG/SVG/WAV/glTF/MP4, `ffprobe`.
- `test_http_api.py`: uwierzytelnienie Basic, odrzucenie insecure LAN, optimistic concurrency, WebSocket, endpointy Ultimate.
- `test_cli_simulation.py`: powtarzalna symulacja, end-to-end CLI eksportu i assetów.
- `test_code_swarm.py`: 4 analizatory, detekcja eval, os.system i sekretów, weryfikacja składni.
- `test_real_local_ci.py`: rzeczywiste uruchomienie dwóch zadań w kopii repozytorium, bez GitHub-hosted Actions.

## Deterministyczny harness

Seed `20261110`, `128` zadań; 20 stron mockowanego API, 20 rekordów SQLite, GGUF v3, DAG 2 zadań, 4 workery, weryfikator Duo, sumaryczne obciążenie grafu, HTTP 401/200, ZIP, AST HMAC, existing discrete-event twin. Każdy niezmiennik jest bool i jest sprawdzany przez test. `scope=DETERMINISTIC_HOST_SIMULATION` wyklucza twierdzenie o fizycznej weryfikacji telefonu.

## Benchmark

`benchmark.json` zawiera 5 serii czasowych, liczbę powtórzeń, min/median/max. Są to pomiary lokalnego hosta, bez gwarancji p99, bez porównania do innych IDE i bez przenoszenia wyników na Android ARM64.

## Etykiety dowodowe

- **Implemented**: kod istnieje i jest dostępny w archiwum.
- **Host tested**: test rzeczywiście uruchomiony na tym hoście.
- **Simulated**: test na deterministycznym modelu, bez fizycznego komponentu.
- **Device verified**: wymaga rzeczywistego testu na Androidzie, którego nie przeprowadzono.
- **Production ready**: wymaga kompletu binariów, podpisu, testu urządzenia i przeglądu bezpieczeństwa; status w osobnym raporcie.

## Upstream source manager

Testy `tests/ultimate/test_upstream_sources.py` sprawdzają przypięte SHA, blokowanie niezaufanych hostów, autoryzację API, brak automatycznego pobierania, lokalny checkout Git, licencje, integralność i CLI. `tools/test_ultimate_browser.py` sprawdza UI biblioteki i świadomą zgodę (HTTP lokalny realny, dane UI mockowane).


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
