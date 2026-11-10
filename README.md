# OMEGA Studio Ultimate — izolowany pakiet źródłowy v1.0.0

**Język interfejsu:** polski. **Wygląd:** Obsidian `#07080A`, 24K Gold `#D4AF37`, platynowa typografia. **Tryb dostawy:** ZIP oraz kopia wybranych zmian źródłowych na `mojealterego/Omega-Studio` (`main`); bez wdrożenia.

OMEGA Studio łączy istniejący kod środowiska Android IDE / AppBuilder, lokalny silnik Actions CI/CD, narzędzia GGUF/Hugging Face i 24 dostawców API z nowym, rzeczywiście działającym modułem **Ultimate Workbench** dla desktopu i lokalnego serwera. Moduł obejmuje crawler organizacji GitHub, katalog SQLite, kontrolowany import źródeł, ograniczony pamięciowo streamer plików, ZIP/RAR, rój z ograniczonym budżetem, generator 2D/3D/3D+czas, audio i MP4, pieczęć AST oraz uwierzytelniony serwer przestrzeni roboczej.

## Uruchomienie lokalnego Workbench

```bash
cd backend
python3 -m pip install -r requirements.txt
export OMEGA_ACTIONS_HOME="$HOME/.omega-studio-local"
python3 -m uvicorn omega_actions.api:create_app --factory --host 127.0.0.1 --port 8080
```

Otwórz `http://127.0.0.1:8080/ultimate`. Lokalny silnik CI/CD działa pod `/`. API chroni losowy token sesji i kontrolę Origin. Panel Ultimate obsługuje polskie nazwy, ma responsywny układ premium i izolowany podgląd NoCode.

## Narzędzia CLI

```bash
cd backend
python3 -m omega_actions.ultimate simulate --seed 20261110 --jobs 128
python3 -m omega_actions.ultimate crawl github --pages 20 --index ./repos.sqlite3
python3 -m omega_actions.ultimate search actions --index ./repos.sqlite3
python3 -m omega_actions.ultimate zip-pack ./moj-projekt ./moj-projekt.zip
python3 -m omega_actions.ultimate zip-extract ./moj-projekt.zip ./rozpakowane
python3 -m omega_actions.ultimate asset gltf ./animacja.gltf
python3 -m omega_actions.ultimate asset mp4 ./animacja.mp4
python3 -m omega_actions.ultimate asset svg ./logo.svg --text "OMEGA Studio"
```

Wyszukiwanie i generowanie lokalne nie wysyłają kodu do zewnętrznych modeli. Crawler uruchamia żądania sieciowe **tylko na polecenie użytkownika**. RAR wymaga odpowiedniego lokalnego dekodera lub licencjonowanego kodera. Generowanie MP4 wymaga lokalnego FFmpeg.

## Zdalny dostęp do obszaru roboczego — przeglądarkowy edytor premium

```bash
export OMEGA_REMOTE_PASSWORD='silne-haslo-o-dlugosci-minimum-12'
python3 -m omega_actions.ultimate.serve ./moj-projekt --bind 127.0.0.1 --port 8080
```

Serwer zdalny udostępnia **interaktywny przeglądarkowy edytor plików** z drzewem katalogów, klawiszem Ctrl+S, kontrolą konfliktów SHA-256, autoryzowanym API i WebSocket. Nasłuch na adresach spoza loopback wymaga certyfikatu i klucza TLS. Dostęp przez Internet wymaga kontrolowanego tunelu VPN / TLS; publiczny niezabezpieczony HTTP nie jest aktywowany.

## Android i VS Code

W paczce znajduje się projekt Android Java, konfiguracja Gradle, AppBuilder Web/Android, menedżer `code-server`, kontrola ELF ARM64, instalator bootstrap oraz skrypty budowy. **Nie jest to gotowy samodzielny APK z Termux/Python/Git/llama.cpp/code-server.** Zestaw binariów zgodnych z prefiksem `/data/data/org.omega.actions/files/usr` nie znajduje się w tej paczce, a SDK/ADB i urządzenie Android nie były dostępne podczas tej weryfikacji. Wcześniejszy APK w katalogu `dist/` jest wyłącznie podglądem interfejsu, bez tych binariów. Dodatkowy walidator `tools/verify_android_apk_release.py` odrzuca takie APK, sprawdza bootstrap i podpis za pomocą `apksigner`. Dokument `PRODUCTION_READINESS_REPORT.md` oddziela faktyczny zakres od żądanej gotowości.

## Zakres źródeł

Załączono `references/MCode.pdf` (11 stron, oryginalne wymagania) i mapę zgodności w `docs/MCode_TRACEABILITY.md`. Wskazane tam adresy organizacji GitHub stron 1–20 są traktowane jako źródło **publicznych metadanych repozytoriów**, nie jako automatyczna zgoda na uruchamianie obcego kodu.

## Weryfikacja

```bash
PYTHONPATH=backend:. python3 -m pytest -q tests backend/tests
node --test tests/test_ui.mjs tests/test_builder.mjs
PYTHONPATH=backend:. python3 -m omega_actions.ultimate simulate
PYTHONPATH=backend:. python3 tools/benchmark_ultimate.py
PYTHONPATH=backend:. python3 tools/test_ultimate_browser.py
```

Dowody, logi, obrazy Chromium i benchmarki są w `validation/ultimate/`. Integralność paczki sprawdza `MANIFEST_SHA256.txt`.

## Granice gwarancji

Symulacja nie stanowi certyfikacji urządzenia, audytu bezpieczeństwa ani pomiaru przewagi nad konkurencją. Szyfrowanie wykorzystuje Argon2id, AES-256-GCM i HMAC-SHA3-256; liczba φ nie jest kluczem ani prymitywem kryptograficznym. Graph diffusion to rzeczywista heurystyka równoważenia obciążeń, nie obliczenia kwantowe.

## Dodatkowe testy i synchronizacja

```bash
PYTHONPATH=backend:. python3 -m pytest -q tests/ultimate/test_remote_ide.py tests/test_android_apk_release_gate.py
PYTHONPATH=backend:. python3 tools/test_remote_ide_browser.py
PYTHONPATH=backend:. python3 tools/verify_android_apk_release.py dist/OMEGA_STUDIO_APPBUILDER_UI_PREVIEW_v1.2.0.apk
```

Ostatnie polecenie **prawidłowo kończy się blokadą**: podglądowy APK nie zawiera kompletnego bootstrap. Szczegóły w `docs/ULTIMATE_SYNC_STATUS.md`.

Synchronizacja `Omega-Studio/main`: źródła edytora HTTP/WebSocket, CLI, walidatora APK, streamera, pieczęci AST i testy. Pełniejsza wersja źródłowa pozostaje w ZIP.

## Integracja oficjalnych repozytoriów open source

Rejestr 11 rzeczywistych repozytoriów, przypięte SHA commitów i sprawdzanie licencji: [docs/OSS_UPSTREAM_INTEGRATION.md](docs/OSS_UPSTREAM_INTEGRATION.md). Pobieranie jest jawne, odtwarzalne i nie uruchamia kodu z repozytorium.

```bash
python3 -m tools.oss_upstreams audit
python3 -m tools.oss_upstreams sync --id termux-packages --allow-network
```
