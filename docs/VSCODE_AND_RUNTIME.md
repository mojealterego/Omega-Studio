# VS Code / code-server w OMEGA Studio

## Implementacja natywna

`CodeServerManager.java` uruchamia `code-server` jako proces potomny z własnego prefiksu, **bez shell interpolation**. Serwer nasłuchuje wyłącznie na `127.0.0.1` i losowym porcie, wymaga hasła sesji generowanego przez `SecureRandom` (32 bajty), ma timeout startowy 20 s i jest zatrzymywany przy zamknięciu głównej aktywności. `RuntimeEnvironment.java` izoluje `HOME`, `PREFIX`, `TMPDIR`, `XDG_CACHE_HOME`, `PATH`, usuwa dziedziczone zmienne wstrzykujące `LD_PRELOAD`, `NODE_OPTIONS` i `PYTHONHOME`.

`CodeEditorActivity.java` otwiera lokalny edytor w **oddzielnym WebView bez `addJavascriptInterface`**. Nie udostępnia operacji uprzywilejowanych środowisku VS Code. Network Security Config dopuszcza niezabezpieczony HTTP tylko dla loopback; pozostały ruch aplikacji wymaga TLS.

`RuntimeHealth.java` wykonuje rzeczywiste `--version` sześciu programów z timeoutem i limitowanym wyjściem. Brak programu oznacza `MISSING`, a błąd procesu `FAILED`, nie symulowany PASS.

## Bezpieczeństwo i ograniczenia

- Inne aplikacje na telefonie mogą próbować łączyć się z loopback; dlatego hasło jest obowiązkowe. Nie włączaj `--auth none`.
- Przeglądarka VS Code i aplikacja główna nie współdzielą mostu JavaScript do Android Keystore.
- Rozszerzenia VS Code zależne od natywnych bibliotek Linuksa mogą nie działać na Androidzie.
- Android może ograniczać liczbę procesów potomnych lub je kończyć; test na rzeczywistym urządzeniu jest konieczny.
- Przeglądarka nie powinna zapisywać hasła sesji w LocalStorage. Po zatrzymaniu serwera hasło jest unieważniane.

## Zakres weryfikacji

Przetestowano lokalnie supervisor procesu za pomocą hostowego serwera testowego, walidację środowiska Java i kompilację źródeł względem stubów Android. **Nie przetestowano rzeczywistego code-server ARM64 na Samsungu ani jego kompatybilności z rozszerzeniami**.
