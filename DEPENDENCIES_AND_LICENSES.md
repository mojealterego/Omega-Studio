# Zależności, licencje i pochodzenie kodu

## Kod pakietu

- Kod Python `backend/` — Apache-2.0 (patrz `backend/LICENSE`).
- Kod projektu głównego i narzędzia — Apache-2.0 (`LICENSE`).
- Java/JS/CSS/HTML w `android/` — źródła projektu; nie kopiowano drzewa
  `termux/termux-app` ani `mojealterego/vscode` do archiwum.
- APK offline preview — zbudowany przez `tools/build_embedded_apk.py`, podpisany
  lokalnym kluczem testowym, nie kluczem dystrybucyjnym użytkownika.

## Python (`backend/pyproject.toml`)

`Python >=3.11`, `setuptools>=68`, `wheel`, `PyYAML>=6,<7`, `fastapi>=0.110,<1`,
`uvicorn>=0.27,<1`, `cryptography>=42,<50`, `argon2-cffi>=23,<26`,
`psutil>=5.9,<8`, `httpx>=0.27,<1`.

Testy lokalne korzystały także z zainstalowanego `pytest` i `playwright`/Chromium.
Dokładny transitive dependency lockfile nie jest dostarczony; zakresy zależności
są jawne w `pyproject.toml`, ale nie stanowią reprodukowalnego SBOM.

## Android

Natywne źródła Java wymagają Gradle/Android Gradle Plugin i Android SDK 35;
`compileSdk=35`, `minSdk=26`, `targetSdk=28`. Podgląd APK budowany jest bez Android SDK.

## Repozytoria referencyjne

- https://github.com/termux/termux-app — Termux Android app (GPLv3 dla części komponentów,
  osobne licencje zależności); **nie dołączono bootstrap ani kopii kodu**.
- https://github.com/mojealterego/vscode — fork Code - OSS (MIT); **tylko punkt odniesienia UI**.
- https://github.com/ggerganov/llama.cpp — silnik GGUF (MIT); **nie dołączono binariów**.
- https://github.com/mojealterego/Digital-Life — **tylko odczyt**; nie kopiowano repo.

Warunki usług GitHub, Hugging Face i OpenAI mają zastosowanie do realnych wywołań API.
Nie przeprowadzono zewnętrznego audytu licencyjnego ani skanowania CVE wszystkich
przyszłych wersji zależności.

## v1.1

Dodano `providers.py` (wykorzystuje istniejący `httpx`), `ProviderCatalog.java` i `RuntimeAssetsInstaller.java` (Java SDK/Android SDK), katalog JSON oraz kod interfejsu bez nowych bibliotek npm. Licencje zewnętrznych Termux/Python/Git/llama.cpp wymagają dołączenia odpowiednich tekstów licencyjnych w finalnej dystrybucji binarnej. Pakiet v1.1 nie dystrybuuje tych binariów.
