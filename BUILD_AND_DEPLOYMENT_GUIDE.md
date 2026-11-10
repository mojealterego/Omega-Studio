# Build & Deployment Guide — offline package, bez wdrażania

## Wymagania hosta

- Python ≥3.11, pip, Node.js dla testów JS, Java 17 dla testów źródeł Android.
- Backend: `backend/requirements.txt` (PyYAML, FastAPI, Uvicorn, cryptography, argon2-cffi, psutil, httpx).
- Opcjonalnie: `rarfile` i `unrar`/`unar` dla RAR, program `rar` dla tworzenia RAR, `ffmpeg` dla MP4.
- Dla natywnego APK: Android SDK compileSdk 35, Gradle, AGP 8.6.1, Android NDK/Termux build toolchain, prawdziwe ARM64 binaria, ADB i fizyczne urządzenie. Te narzędzia nie są zawarte w dostarczonym ZIP.

## Start desktop / localhost

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OMEGA_ACTIONS_HOME="$HOME/.omega-studio"
python3 -m uvicorn omega_actions.api:create_app --factory --host 127.0.0.1 --port 8080
```

Panel Ultimate: `http://127.0.0.1:8080/ultimate`. Lokalny CI/CD: `/`. Zmienna `OMEGA_VAULT_PASSWORD` aktywuje szyfrowany skarbiec. Zewnętrzne API są wyłączone bez `OMEGA_ENABLE_PAID_AI=true` i jawnego potwierdzenia kosztu żądania.

## Zdalny dostęp

```bash
export OMEGA_REMOTE_PASSWORD='minimum-12-znakow-i-silne'
python3 -m omega_actions.ultimate serve ./workspace --bind 127.0.0.1 --port 8080
# Poza loopback: --bind 0.0.0.0 --tls-cert cert.pem --tls-key key.pem
```

Zewnętrzne połączenia powinny przechodzić przez VPN lub HTTPS. Brak automatycznego wystawiania portu na publiczny Internet.

## Budowa Android

Kod Java i Gradle znajduje się w `android/`; pełny runtime musi odpowiadać `applicationId=org.omega.actions` i prefiksowi `/data/data/org.omega.actions/files/usr`. `tools/build_custom_termux.sh` pobiera przypięty commit upstream Termux i uruchamia budowę pakietów w Dockerze. `tools/assemble_runtime_from_bootstrap.py` importuje binaria, `tools/verify_runtime_bundle.py` kontroluje kompletność, a `tools/build_full_apk.sh` jest bramką SDK, podpisu i fizycznego smoke testu.

Bramka odrzuca pusty bootstrap, niewłaściwy ELF, brakujące binaria, brak SDK i brak ADB. To zamierzone działanie fail-closed, a nie błąd skryptu.

## Testy

```bash
PYTHONPATH=backend:. python3 -m pytest -q tests backend/tests
node --test tests/test_ui.mjs tests/test_builder.mjs
PYTHONPATH=backend:. python3 tools/benchmark_ultimate.py
PYTHONPATH=backend:. python3 tools/test_ultimate_browser.py
python3 tools/verify_android_sources.py
```

Test Chromium w tym środowisku wykonuje prawdziwy smoke test HTTP, a przeglądarka używa kontrolowanego mock transportu JS, ponieważ jej polityka sieciowa blokuje nawigację do lokalnych portów. Rozdzielenie dowodów jest jawne w `browser_result.json`.

## Budowa ZIP

`tools/package_ultimate.py` generuje deterministyczny ZIP, manifest SHA-256 i weryfikuje rozpakowanie oraz CRC. Repozytoria `Omega-Studio` i `Digital-Life` nie są miejscami docelowymi zapisu.

## Instalacja i wdrożenie

Pakiet nie instaluje niczego samoczynnie, nie modyfikuje GitHub Actions, nie publikuje wydań i nie przeprowadza migracji produkcyjnych. Uruchomienie na urządzeniu pozostaje świadomą decyzją właściciela środowiska.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
