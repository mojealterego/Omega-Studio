# OMEGA Studio Ultimate — rozwój v2.0.0

**Źródło wymagań:** `reference/MCode.pdf` (11 stron). **Tryb:** lokalny, open source, z rozróżnieniem testów hostowych i Android. **Repozytorium:** `mojealterego/Omega-Studio/main`.

Nowe komponenty: `quantum_topology.py`, `self_healing_ast.py`, `holographic_memory.py`, `neuromorphic_synapse.py`, `adaptive_ci.py`, `network_chaos.py`, rzeczywisty ARM64 ELF w `android/app/src/main/jniLibs/arm64-v8a/` i sekcja Hyperengineering Lab w panelu `/ultimate`. Szczegóły: `docs/MCODE_11_PAGE_TRACEABILITY.md`, `docs/HYPERENGINEERING_V2.md`, `docs/UPLOADED_SOURCE_AUDIT.md`.

**Ważne:** dołączony APK to podpisany podgląd interfejsu z natywnym ELF, nie pełna dystrybucja Termux/VS Code/Python/Git/llama.cpp. Kod źródłowy upstream nie jest wykonywalnym bootstrap Android. Wydanie produkcyjne wymaga rzeczywistych zgodnych binariów i testu na urządzeniu; raport nie zastępuje tych dowodów.

## Uruchomienie

```bash
cd backend
python3 -m pip install -r requirements.txt
export OMEGA_ACTIONS_HOME="$HOME/.omega-studio-local"
python3 -m uvicorn omega_actions.api:create_app --factory --host 127.0.0.1 --port 8080
```

`http://127.0.0.1:8080/ultimate` — interfejs premium. API używa lokalnego tokenu sesji i kontroli Origin. Zdalny dostęp spoza loopback wymaga TLS i uwierzytelnienia.

## Testy

```bash
PYTHONPATH=backend:. python3 -m pytest -q backend/tests builder/tests tests/ultimate tests/test_android_apk_release_gate.py tests/test_backend_asset_v11.py tests/test_runtime_bundle_v11.py
node --test tests/test_ui.mjs tests/test_builder.mjs
PYTHONPATH=backend:. python3 tools/test_ultimate_browser.py
python3 -m tools.build_native_arm64 android/app/src/main/jniLibs/arm64-v8a/libomega_runtime.so
python3 -m tools.build_embedded_apk dist/OMEGA_Studio_Android_ARM64_Preview_v2.0.0.apk
```

Pełny przewodnik w `BUILD_AND_DEPLOYMENT_GUIDE.md` i `docs/ANDROID_BUILD.md`.

---

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

## Biblioteka źródeł Open Source (przypięte SHA)

OMEGA Studio ma katalog 14 oficjalnych projektów: Termux, Termux Packages, code-server, Code-OSS **1.85.1**, llama.cpp, Git, CPython, Node.js, Monaco, xterm.js, Actions Runner i Hugging Face Hub. Lokalny menedżer pobiera je na żądanie, weryfikuje commit, licencję i integralność checkoutu. Zobacz [dokumentację upstream](docs/UPSTREAM_SOURCE_INTEGRATION.md). Pobranie kodu źródłowego nie oznacza wbudowania gotowych binariów ARM64 w APK.
