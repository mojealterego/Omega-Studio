# OMEGA Studio — Sovereign AppBuilder / Local CI v1.2.0

**Polski, lokalny edytor Code/NoCode** z autorskim AppBuilderem dla statycznych aplikacji webowych i aplikacji natywnych Android. Zawiera ponadto istniejący backend Python CI/CD, moduły GitHub, GGUF, Hugging Face, czat wielomodelowy i katalog dostawców API.

## Co działa w dostarczonym kodzie

- Wizualny AppBuilder: strony, komponenty, edycja treści, nawigacja, trzy motywy, podgląd w izolowanej ramce, import/eksport JSON.
- Generator **prawdziwych źródeł natywnej aplikacji Android** (Java `Activity`, `TextView`, `Button`, `EditText`) oraz statycznej aplikacji webowej (HTML/CSS/JS) w archiwum ZIP.
- Deterministyczny generator Python z kontrolą schematu, ochroną przed XSS i wstrzykiwaniem kodu Java, sumami SHA-256 i CLI.
- Offline APK **podglądowy** z interfejsem AppBuilder oraz systemową powłoką Android; nie korzysta z adresu `127.0.0.1:8765`.
- Backend Python z istniejącym silnikiem CI/CD, API, narzędziami GitHub, GGUF i Hugging Face, uruchamiany osobno na maszynie z Pythonem.

## Uruchomienie AppBuildera

### Z poziomu przeglądarki lub APK podglądowego

Otwórz `android/app/src/main/assets/index.html` w przeglądarce lub zainstaluj `dist/OMEGA_STUDIO_APPBUILDER_UI_PREVIEW_v1.2.0.apk`. Zakładka **AppBuilder** zawiera edytor NoCode i przycisk **Eksportuj projekt ZIP**. W systemie Android zachowanie pobierania ZIP zależy od obsługi `blob:` przez WebView; eksport w Pythonie działa niezależnie.

### CLI — eksport deterministyczny

```bash
python -m builder.omega_builder validate builder/examples/premium-app.json
python -m builder.omega_builder build builder/examples/premium-app.json --output omega-app.zip
```

Wygenerowany projekt webowy nie wymaga żadnej usługi płatnej. Wygenerowany projekt Android wymaga Gradle, Android SDK 35 i kompilacji na odpowiednim środowisku.

## CI/CD i backend

```bash
cd backend
python -m pip install -e .
python -m omega_actions serve --host 127.0.0.1 --port 8765
```

Powyższy backend **nie uruchamia się automatycznie w APK podglądowym**. Do wykonania lokalnych workflowów nie trzeba uruchamiać płatnych GitHub-hosted Actions, lecz niektóre workflowy wymagają zewnętrznych narzędzi i środowisk.

## Granica binarnej gotowości Android

APK podglądowy **nie zawiera** działających binariów Termux, Python, Git ani llama.cpp. W tym środowisku nie ma Android SDK/Gradle ani zgodnego pakietu bootstrap dla `org.omega.actions`; nie wykonano testu instalacji na Samsungu S24 Ultra. Skrypt `tools/build_android_release.sh` wymusza weryfikację binariów przed próbą wydania pełnej aplikacji. Symulacja nie zastępuje uruchomienia binariów ARM64 na telefonie.

## Bezpieczeństwo

- Brak automatycznych wywołań płatnych API.
- Import projektów ograniczony rozmiarem i schematem; nawigacja tylko do lokalnych stron.
- Podgląd `iframe` z `sandbox` bez uprawnień.
- Generowany web z CSP, tekst użytkownika kodowany HTML; natywny Java z tekstami Base64.
- Wersja podglądowa nie stanowi bezpiecznego środowiska do wykonywania niezaufanych workflowów CI.
- Klucze API przechowywane przez Android Keystore są zaimplementowane w źródłach natywnych, **nie w APK podglądowym**.

## Repozytoria

Repozytorium projektu: `https://github.com/mojealterego/Omega-Studio`.
Repozytorium Digital-Life jest używane wyłącznie jako kontekst architektoniczny i nie zostało zmodyfikowane. Żadnych GitHub-hosted Actions nie uruchomiono.

Zobacz `docs/APPBUILDER.md`, `docs/RELEASE_STATUS_v12.md`, `PRODUCTION_READINESS_REPORT.md` i `validation/`.
