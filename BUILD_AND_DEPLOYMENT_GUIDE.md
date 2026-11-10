# Build & Deployment Guide — v1.2.0

## Lokalny AppBuilder

Python 3.11+ bez zewnętrznych zależności: `python -m builder.omega_builder build builder/examples/premium-app.json --output app.zip`.

## Testy

`PYTHONPATH=.:backend python -m pytest -q backend/tests builder/tests tests/test_backend_asset_v11.py tests/test_runtime_bundle_v11.py`.

`node --test tests/test_ui.mjs tests/test_builder.mjs`.

`python -m tools.verify_generated_native` — kompilacja Java względem stubów.

## APK podglądowy

`python -m tools.build_embedded_apk dist/OMEGA_STUDIO_APPBUILDER_UI_PREVIEW_v1.2.0.apk`.

Ten APK nie jest produkcyjnym pakietem z Termux.

## Pełny APK Android

`bash tools/build_android_release.sh` wymaga Android SDK 35, Gradle, zgodnego bootstrap Termux ARM64 dla `org.omega.actions` i prawdziwych ELF `bash`, `python`, `git`, `llama-cli`. Weryfikacja strukturalna nie dowodzi poprawnego wykonania na urządzeniu.

## Eksport wygenerowanej aplikacji Android

Rozpakuj wygenerowane `omega-app.zip`, przejdź do `android/`, uruchom Gradle z Android SDK i podpisz wynik własnym kluczem. Nie uruchamiaj workflowów GitHub Actions w celu kompilacji, jeżeli budżet ma pozostać zerowy.
