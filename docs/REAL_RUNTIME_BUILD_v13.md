# OMEGA Studio v1.3 — kompletna ścieżka budowania runtime Android ARM64

## Status i dowody

Implementacja v1.3 obejmuje walidator ELF64/AArch64/PIE, deterministyczny pakowacz runtime, bezpieczny importer bootstrap Termux, natywny instalator Android, weryfikację rzeczywistego uruchomienia sześciu poleceń, lokalny code-server z hasłem sesji, podpisywanie wydania i bramkę produkcyjną. **Nie obejmuje jeszcze skompilowanych binariów ARM64**, gdyż środowisko robocze nie udostępnia Android SDK/NDK, Docker ani dostępu sieciowego do źródeł i zależności. Nie ma też testu na urządzeniu Android 17. Żadna lokalna symulacja nie zastępuje tych dowodów.

## Identyfikator pakietu i ABI

- Android `applicationId`: `org.omega.actions`.
- Docelowy prefix: `/data/data/org.omega.actions/files/usr`.
- ABI: `arm64-v8a` / ELF64 little-endian AArch64 PIE.
- Obowiązkowe: `bin/bash`, `bin/python`, `bin/git`, `bin/llama-cli`, `bin/node`, `bin/code-server` i komplet zasobów aplikacji code-server.
- **Nie kopiować** plików binarnych ani bibliotek z oficjalnego `com.termux` — ścieżki i zależności są inne.

## Zewnętrzny build bez GitHub Actions

Na Linux x86_64 z Dockerem, Android SDK, Gradle, dostępem do źródeł i dużą ilością miejsca:

1. Wybierz i zweryfikuj **konkretny SHA** commitu źródeł `agnostic-apollo/termux-packages` (gałąź `infra-improvs` rekomendowana przez wiki Termuxa dla własnych bootstrapów). Nie uruchamiaj przypadkowych forków ani skryptów z niesprawdzonych źródeł.
2. Skompiluj `code-server` dla *tego samego* prefixu i ABI, wraz z zależnościami Node; skopiuj wynik instalacji do lokalnego katalogu `editor-prefix/` z zachowaniem struktury `bin/`, `share/` i `lib/`. **Samo pobranie paczki dla Linux ARM64/glibc nie jest poprawnym zamiennikiem Android/Bionic.**
3. Uruchom skrypt:

```bash
bash tools/build_custom_termux.sh \
  --termux-ref <40-znakowy-SHA-zaufanego-commitu> \
  --editor-prefix /absolute/path/editor-prefix \
  --work-dir /absolute/path/workdir
```

Skrypt buduje `python`, `git`, `llama-cpp` i `nodejs` z ich zależnościami, po czym importer łączy bootstrap z zasobami code-server. Wymaga dostępu do Internetu podczas kompilacji, **ale docelowe APK jest instalowane bez osobnej aplikacji Termux i bez pobierania binariów przy pierwszym uruchomieniu**.

4. Zbuduj podpisany release:

```bash
export ANDROID_HOME=/absolute/path/android-sdk
export OMEGA_KEYSTORE=/absolute/path/release.jks
export OMEGA_KEYSTORE_PASSWORD='...'
export OMEGA_KEY_ALIAS='omega-release'
export OMEGA_KEY_PASSWORD='...'
bash tools/build_android_release.sh
```

Nie zapisuj haseł ani keystore w repozytorium. `build_android_release.sh` kończy się błędem, jeśli brakuje runtime, SDK, Gradle, podpisu lub wymaganych zasobów w APK. Brak `gradlew` oznacza konieczność użycia lokalnej instalacji Gradle zgodnej z AGP 8.6.1.

## Weryfikacja na urządzeniu

Po instalacji APK na docelowym Androidzie:

1. Uruchom instalację bootstrap wewnątrz OMEGA Studio. Instalator sprawdza SHA-256 i prefix, rozpakowuje do katalogu staging, blokuje Zip Slip i symlinki wychodzące poza prefix, uruchamia testy binariów i dopiero wtedy zapisuje marker integralności.
2. W panelu **VS Code → Sprawdź binaria** uruchom testy `bash`, `python`, `git`, `llama-cli`, `node` i `code-server`. Każdy test musi zwrócić `PASS` z rzeczywistym wyjściem procesu. Niezgodność jednego komponentu blokuje gotowość.
3. Włącz `code-server` — wyłącznie na `127.0.0.1` z losowym hasłem; interfejs IDE działa w osobnej Activity bez uprzywilejowanego JS bridge.
4. Wykonaj test importu i inferencji GGUF oraz lokalnego workflow CI/CD na repozytorium testowym. Zweryfikuj zachowanie po restarcie, timeout, odzyskiwanie stanu, podpis APK i zgodność z ograniczeniami Android 17.
5. Zapisz dowody `adb logcat`, wyniki testów i sumy SHA-256. **Nie oznaczaj 100% bez tych wyników.**

## Znane ryzyka

- Android 10+ i nowe wersje systemu ograniczają wykonywanie plików w zapisywalnym katalogu aplikacji; obecny profil sideload ma `targetSdk=28`. Zgodność z Android 17 wymaga sprawdzenia na fizycznym urządzeniu.
- `code-server` na Androidzie może nie obsługiwać wszystkich rozszerzeń natywnych VS Code; część wymaga glibc/Linux i nie jest zgodna z Android/Bionic.
- `llama.cpp` zależy od ABI, architektury, bibliotek i parametrów modelu; sama obecność ELF nie dowodzi poprawnej inferencji.
- Android Keystore i lokalny code-server muszą być objęte testem bezpieczeństwa. Nie uruchamiaj `code-server --auth none` ani na `0.0.0.0`.
- Rozmiar kompletnego bootstrapu może być duży; brak rozdzielenia ABI w tej wersji.

## Źródła pierwotne

- https://github.com/termux/termux-app
- https://github.com/termux/termux-packages/wiki/For-maintainers
- https://github.com/agnostic-apollo/termux-packages/tree/infra-improvs
- https://coder.com/docs/code-server/termux
- https://github.com/ggml-org/llama.cpp
