# OMEGA Studio v1.2.0 — evidence ledger

| Obszar | Dowód | Status |
|---|---|---|
| AppBuilder Python | `validation/full_python_tests.log` | Lokalnie przetestowany |
| AppBuilder JavaScript | `validation/full_js_tests.log` | Lokalnie przetestowany |
| UI Chromium | `validation/browser.log`, screenshoty | Test w izolowanej przeglądarce |
| Java generator | `validation/native_java.log` | Kompilacja ze stubami |
| Android źródła | `validation/android_sources.log` | Kompilacja ze stubami |
| APK preview | `validation/apk_preview_build.log` | Struktura i podpis v2 zweryfikowane |
| Pełny APK Termux/Python/Git/llama.cpp | `tools/verify_runtime_bundle.py` | Brak zgodnego bootstrap; bramka produkcyjna zablokowana |
| Instalacja na fizycznym Androidzie | brak dostępu do urządzenia | Niepotwierdzona |
| GitHub Actions | żadne nieuruchomione | Brak wykorzystania minut przez te prace |
| Digital-Life | tylko odczyt | Brak zmian |

Audyty zewnętrzne nie zostały przeprowadzone. Wyniki testów symulacyjnych potwierdzają tylko zachowanie modelu testowego. Brak dowodów przewagi wydajnościowej nad komercyjnymi rozwiązaniami CI/CD.
