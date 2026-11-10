# OMEGA Studio 1.3 — rzeczywiste binaria ARM64, bez zewnętrznego Termux

## Kontrakt wydania

Jedyny akceptowany artefakt to APK zawierający archiwum `bootstrap-aarch64-v8a.zip`, manifest `bootstrap-prefix.txt` oraz SHA-256. Bootstrap **musi być zbudowany dla**:

`/data/data/org.omega.actions/files/usr`

Archiwum musi zawierać działające programy `bin/bash`, `bin/python`, `bin/git`, `bin/llama-cli`, `bin/node`, `bin/code-server`, ich zależności oraz pliki edytora `code-server`. `bin/code-server` może być skryptem z poprawnym shebang; pięć pozostałych poleceń musi być natywnym ELF64/LE/AArch64. Wszystkie zależności natywne muszą być zgodne z Android/Bionic; pliki ELF glibc/Linux są odrzucane.

**Nie można użyć oficjalnego bootstrap z `com.termux`** bez przebudowania pakietów. Zmiana nazwy APK nie zmienia skompilowanych ścieżek pakietów. Zobacz oficjalne dokumenty `termux/termux-app` i `termux/termux-packages`.

## Zewnętrzna kompilacja pakietów (Linux, Docker, Android SDK)

1. Pobierz `termux/termux-packages` i `termux/termux-app` z oficjalnych repozytoriów oraz przypnij rewizje Git SHA; zapisz je w rejestrze zależności.
2. W **osobnej kopii roboczej** `termux-packages` ustaw `TERMUX_APP_PACKAGE=org.omega.actions` w `scripts/properties.sh` zgodnie z aktualną wersją projektu. Wyczyść wcześniejsze artefakty kompilacji po zmianie pakietu.
3. W kontenerze `ghcr.io/termux/package-builder` zbuduj pakiety i ich zależności dla `aarch64`: bazowy bootstrap, Python, Git, Node.js i `llama-cpp`. Dokumentacja Termux opisuje `scripts/run-docker.sh`, `scripts/build-bootstraps.sh` i opcję `--add`; jej składnię należy sprawdzić w używanej, przypiętej rewizji.
4. Zbuduj `code-server` **dla tego samego prefiksu i Android ARM64**, razem z kompatybilnym Node i zależnościami. Oficjalny `coder/code-server` dokumentuje wariant Termux; paczki TUR z prefiksem `com.termux` nie są zamiennikiem builda `org.omega.actions`.
5. Wygeneruj drzewo `usr/` zawierające wszystkie sześć poleceń i edytor, zachowując prawa wykonywania, symlinki i licencje.

## Import do projektu

Jeśli dysponujesz kompletnym drzewem `usr/` z własnego builda:

```bash
python3 -m tools.runtime_supply_chain \
  --prefix-root /path/to/verified/usr \
  --assets android/app/src/main/assets \
  --package org.omega.actions
```

Jeśli masz archiwum Termux bootstrap i oddzielnie skompilowany code-server:

```bash
python3 -m tools.assemble_runtime_from_bootstrap \
  --bootstrap /path/to/bootstrap-aarch64.zip \
  --editor-prefix /path/to/code-server-prefix \
  --assets android/app/src/main/assets \
  --package org.omega.actions
```

Jeśli masz już kompletne archiwum bootstrap dla właściwego prefiksu:

```bash
printf '%s\n' '/data/data/org.omega.actions/files/usr' > /tmp/omega-prefix.txt
python3 -m tools.prepare_runtime_release \
  --archive /path/to/bootstrap-aarch64-v8a.zip \
  --prefix-manifest /tmp/omega-prefix.txt \
  --assets android/app/src/main/assets
```

Importer nie pobiera żadnych binariów i **odrzuca niekompletne paczki**. Weryfikacja statyczna obejmuje architekturę, interpreter Android, nagłówki ELF, ścieżki, symlinki, SHA-256 i kompletność code-server. Syntetyczny ELF z testów nigdy nie stanowi dowodu działania.

## Budowa i test na fizycznym telefonie

W środowisku z Android SDK 35, Gradle, ADB i `apksigner`:

```bash
bash tools/build_full_apk.sh
```

Skrypt kolejno: pakuje źródła Pythona, weryfikuje pełny runtime, buduje APK debug, weryfikuje podpis, instaluje na **fizycznym urządzeniu ARM64**, uruchamia aplikację i wykonuje sześć rzeczywistych poleceń `--version` z prywatnego prefiksu aplikacji. W razie dowolnego błędu kończy się kodem niezerowym i nie publikuje nazwy `DEVICE_VERIFIED`.

APK debug nie jest podpisanym wydaniem produkcyjnym. Do dystrybucji należy dodatkowo przeprowadzić niezależny audyt, testy zgodności Android, signing release własnym kluczem i test ponownej instalacji/aktualizacji.

## Blokery w bieżącym środowisku

- Brak połączenia sieciowego do pobrania pakietów i źródeł builda.
- Brak Android SDK, Gradle, ADB i `apksigner`.
- Brak skompilowanych, zgodnych binariów ARM64 dla `org.omega.actions`.
- Brak fizycznego testu na urządzeniu docelowym.

W tych warunkach **nie powstał pełny APK**. Dostarczany jest kod, testy i bezpieczny proces budowania, który nie akceptuje fikcyjnego sukcesu.
