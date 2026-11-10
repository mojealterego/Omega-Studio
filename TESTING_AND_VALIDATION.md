# Testy OMEGA Studio v1.2.0

## Faktyczne uruchomienia lokalne

- `PYTHONPATH=.:backend python -m pytest -q backend/tests builder/tests tests/test_backend_asset_v11.py tests/test_runtime_bundle_v11.py` — **121 passed, 4 subtests passed, 0 failed** (`validation/full_python_tests.log`).
- `node --test tests/test_ui.mjs tests/test_builder.mjs` — **15 passed, 0 failed** (`validation/full_js_tests.log`).
- `python -m tools.verify_android_sources` — **8 plików źródłowych Java kompiluje się ze stubami** (`validation/android_sources.log`).
- `python -m tools.verify_generated_native` — **generowany projekt natywny Java kompiluje się ze stubami** (`validation/native_java.log`).
- `python tools/test_builder_browser.py` — **E2E interfejsu Chromium PASS**, bez błędów JS, screenshot desktop i mobile (`validation/browser.log`). Test korzysta z inlinowanych assetów, ponieważ polityka środowiska blokuje nawigację do lokalnych adresów.
- `python -m tools.build_embedded_apk ...` — **APK podglądowy z podpisem v2 PASS** (`validation/apk_preview_build.log`).
- `python -m tools.verify_runtime_bundle` — **BLOCKED (exit 2)**, brak zgodnego bootstrap Termux ARM64 (`validation/runtime_release_gate.log`). Nie jest to zaliczony test runtime.

## Zakres dowodowy

Testy Python/JS i kompilacja ze stubami nie potwierdzają działania pełnego Android SDK, natywnego bootstrap, Git ani llama.cpp na telefonie. Zewnętrzny audyt nie został wykonany. Nie przeprowadzono benchmarków porównawczych z GitHub Actions.

## Testy integracji oficjalnych repozytoriów (10.11.2026)

```bash
PYTHONPATH=.:backend python3 -m pytest -q tests backend/tests
node --test tests/test_ui.mjs tests/test_builder.mjs
python3 -m tools.oss_upstreams audit
```

Wyniki: **216 testów Python PASS + 4 podtesty PASS**, **15 testów JavaScript PASS**. Własne testy nowego synchronizatora obejmują rzeczywisty lokalny checkout Git, SHA commita, licencję, wykrywanie zmian, brak nadpisywania oraz odmowę pracy na niebezpiecznych ścieżkach. `build_custom_termux.sh` odrzuca ref niezgodny z lock. Wyniki nie stanowią testu fizycznego Androida ani kompilacji Termux.
