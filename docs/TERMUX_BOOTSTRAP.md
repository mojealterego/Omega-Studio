# Termux wewnątrz własnego APK — wymagania binarne

**Fakt techniczny:** Termux nie jest tylko emulatorem terminala. Oprócz Android Activity wymaga zestawu binariów i bibliotek skompilowanych dla konkretnego `TERMUX_APP_PACKAGE` i `$PREFIX`. Oficjalne pakiety `com.termux` nie są kompatybilne z prefiksem `org.omega.actions`.

## Zasada identyfikatora pakietu

Projekt natywny używa `org.omega.actions`. Jego docelowy prefix to `/data/data/org.omega.actions/files/usr`. Wymaga to przebudowania bootstrap oraz wszystkich pakietów natywnych dla tego prefiksu. Nie wolno podpisywać i rozprowadzać oryginalnego APK Termux jako OMEGA Studio.

Oficjalne źródła:
- https://github.com/termux/termux-app
- https://github.com/termux/termux-packages
- https://github.com/termux/termux-packages/wiki/For-maintainers

## Natywny instalator w kodzie

`TermuxBootstrapInstaller.java` weryfikuje trzy zasoby w `android/app/src/main/assets/`:

- `bootstrap-aarch64-v8a.zip` — bootstrap skompilowany dla `org.omega.actions`.
- `bootstrap-aarch64-v8a.sha256` — SHA-256 powyższego archiwum.
- `bootstrap-prefix.txt` — dokładny tekst `/data/data/org.omega.actions/files/usr`.

Następnie stosuje staging, ochronę przed Zip Slip, limity rozmiaru, tworzenie symlinków z `SYMLINKS.txt` i finalizację katalogu `files/usr`. Archiwum i manifesty **nie są częścią obecnego ZIP**, ponieważ nie zostały zbudowane dla docelowej architektury i prefiksu. Nie należy podmieniać ich archiwum oficjalnego Termuxa.

## Python, Git i języki

Aby działały wewnątrz APK, bootstrap musi zawierać zgodne `bash`, `python`, `git`, `nodejs`, `clang`, `rust`, `golang` i ich zależności, zbudowane dla `arm64-v8a`. Rozmiar takiej dystrybucji będzie istotnie większy niż obecny APK podglądowy. Skrypty i narzędzia Pythona w katalogu `backend/` wymagają instalacji w tym środowisku.

## Ograniczenia Android 12+

Android może ograniczać liczbę procesów potomnych i zabijać długie zadania. Uruchamianie plików wykonywalnych z zapisywalnego katalogu aplikacji podlega dodatkowym restrykcjom zależnym od targetSdk i polityk systemu. Źródłowy projekt Android Studio ustawia targetSdk 28 dla profilu sideload; APK podglądowy targetuje 35 i uruchamia tylko systemową powłokę. **Działanie na Androidzie 17 nie zostało zweryfikowane**.
