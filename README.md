# OMEGA Studio 1.3.0 — Sovereign Android IDE / AppBuilder

Polskojęzyczne środowisko Android-first z interfejsem **Obsidian & 24K Gold**, lokalnym AppBuilderem Code/NoCode, backendem Python CI/CD, GitHub, czatem AI, integracją GGUF i natywnym adapterem do code-server.

## Dostarczony kod

- AppBuilder: edytor stron i komponentów, generowanie projektów Web HTML/CSS/JS oraz natywnych źródeł Android Java.
- Edytor kodu i terminal z asynchronicznym mostem Android; lokalny silnik CI/CD Python i obsługa GGUF.
- Integracja VS Code przez `code-server`/Node: proces lokalny, losowe hasło, loopback, izolowany WebView bez mostu JavaScript.
- Menedżer binariów: rygorystyczna weryfikacja SHA-256, ELF64/ARM64/Android linker, symlinków, prefiksu pakietu i kompletności zasobów edytora.
- Automatyczna instalacja zasobów na pierwszym uruchomieniu **wyłącznie jeśli kompletny bootstrap jest w APK**.
- Bezpieczny release gate: nie publikuje nazwy `DEVICE_VERIFIED` bez wykonania sześciu binariów na fizycznym urządzeniu.
- Katalog 24 dostawców API, klucze w Android Keystore w kodzie natywnym; opłaty zewnętrznych modeli wymagają jawnej zgody.

## Weryfikacja

```bash
PYTHONPATH=.:backend python3 -m pytest -q tests backend/tests
node --test tests/test_ui.mjs tests/test_builder.mjs
python3 tools/verify_android_sources.py
bash tools/build_full_apk.sh
```

Ostatnie polecenie jest **celowo blokowane**, dopóki nie ma realnego bootstrap i narzędzi Android. Nie wykonuje fikcyjnego builda.

## Ukończenie binarnego APK

Zobacz [docs/NATIVE_RUNTIME_BUILD.md](docs/NATIVE_RUNTIME_BUILD.md) i [docs/VSCODE_AND_RUNTIME.md](docs/VSCODE_AND_RUNTIME.md).

**Aktualny stan: kod źródłowy i testy integracji; NIE ukończony samodzielny APK.** Nie ma zgodnego bootstrap Termux/Python/Git/llama.cpp/Node/code-server, nie było testu na fizycznym Samsungu. Wcześniejszy APK v1.2.0 to wyłącznie podgląd UI. Żadnych płatnych GitHub Actions nie uruchomiono.
