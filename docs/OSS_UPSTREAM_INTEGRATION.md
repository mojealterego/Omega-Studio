# OMEGA Studio — integracja rzeczywistych projektów open source

## Model dostarczania

OMEGA Studio korzysta z oryginalnych projektów jako zewnętrznych źródeł kodu, nie z imitacji ich funkcji. Plik `config/upstreams.lock.json` zawiera 11 repozytoriów z konkretnymi identyfikatorami commitów SHA-1 Git, licencjami i przeznaczeniem. Identyfikator commita nie jest sumą SHA-256 pobranego archiwum; oba rodzaje kontroli mają inne zastosowania.

### Komponenty

| Moduł | Źródło | Licencja | Zastosowanie |
|---|---|---|---|
| Terminal Android | [termux/termux-app](https://github.com/termux/termux-app) | GPL-3.0-only | Terminal, integracja Android |
| Pakiety ARM64 | [termux/termux-packages](https://github.com/termux/termux-packages) | Według pakietu | Bootstrap, Bash, Python, Git, Node.js, llama-cpp |
| Edytor przeglądarkowy | [coder/code-server](https://github.com/coder/code-server) | MIT | VS Code przez lokalny serwer |
| Referencja 1.85.1 | [microsoft/vscode](https://github.com/microsoft/vscode/tree/1.85.1) | MIT (Code - OSS) | Punkt odniesienia dla funkcji edytora |
| GGUF | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | Inferencja lokalna na ARM64 |
| Git | [git/git](https://github.com/git/git) | GPL-2.0-only | Kontrola wersji |
| Python | [python/cpython](https://github.com/python/cpython) | PSF | Interpreter i standardowa biblioteka |
| GitHub CLI | [cli/cli](https://github.com/cli/cli) | MIT | Operacje GitHub |
| Monaco | [microsoft/monaco-editor](https://github.com/microsoft/monaco-editor) | MIT | Edytor i podświetlanie składni |
| Tree-sitter | [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) | MIT | Parsowanie przyrostowe kodu |
| Hugging Face | [huggingface/huggingface_hub](https://github.com/huggingface/huggingface_hub) | Apache-2.0 | Katalog modeli i pobieranie |

GitHub.com jako usługa nie jest tym samym co otwartoźródłowy klient GitHub CLI. Otwarty kod `microsoft/vscode` nie oznacza automatycznego prawa do redystrybucji komercyjnej dystrybucji Visual Studio Code, jej znaków i zasobów. Termux-app i Git mają licencje copyleft; każda redystrybucja binariów wymaga zachowania odpowiednich informacji licencyjnych i udostępnienia właściwego kodu źródłowego. Weryfikacja pełnej zgodności prawnej musi obejmować także zależności transytywne i zasoby.

## Bezpieczne pobieranie i kontrola źródeł

```bash
python3 -m tools.oss_upstreams audit
python3 -m tools.oss_upstreams resolve --id termux-packages
python3 -m tools.oss_upstreams sync --id termux-packages --destination vendor/upstreams --allow-network
python3 -m tools.oss_upstreams verify --id termux-packages --destination vendor/upstreams
```

`sync` wymaga jawnego `--allow-network`, wykonuje checkout wyłącznie do przypiętego SHA, blokuje protokół `file://` w trybie sieciowym, nie uruchamia submodułów, nie nadpisuje istniejących checkoutów i zapisuje `.omega-source.json` z SHA-256 pliku licencji. Testy integracyjne używają rzeczywistego lokalnego repozytorium Git, bez dostępu do internetu.

## Wytworzenie rzeczywistego Android ARM64

```bash
bash tools/build_custom_termux.sh \
  --editor-prefix /ścieżka/do/zbudowanego/code-server \
  --work-dir /ścieżka/do/pustego/katalogu
```

`build_custom_termux.sh` pobiera identyfikator źródła `termux-packages` z pliku lock. Odrzuca inną wartość `--termux-ref` zanim uruchomi Dockera lub pobieranie. Następnie wykorzystuje upstream `scripts/build-bootstraps.sh` do kompilacji `python`, `git`, `llama-cpp`, `nodejs` i zależności dla `org.omega.actions`. Nie miesza pakietów przeznaczonych dla `com.termux`.

`code-server` wymaga osobnego, zgodnego z Androidem wydania z natywnymi zależnościami Node.js; jego oficjalna instrukcja Termux opisuje instalację przez repozytorium TUR lub npm. Pakiety TUR dla `com.termux` nie są równoważne pakietom zbudowanym dla `org.omega.actions`. Dostarczenie źródła `code-server` i menedżera procesu nie oznacza automatycznie, że binarium jest już w APK.

Źródła `llama.cpp` mają oficjalną ścieżkę Android NDK oraz recepturę `llama-cpp` w Termux. Wydanie APK przechodzi kontrolę ELF64/AArch64, ścieżek `$PREFIX`, sum SHA-256 i uruchomienia komend na urządzeniu. Testy hostowe i symulacje nie zastępują uruchomienia binariów na Androidzie.

## Bezpieczeństwo

Pobieranie źródeł z zewnętrznych repozytoriów nie daje automatycznej zgody na wykonywanie ich kodu. Przed wykonaniem skryptów budowania należy stosować izolowane środowisko budowania, ograniczenia zasobów, skan zależności, kontrolę licencji i artefaktów oraz kontrolę publikacji. Pobrane projekty nie są automatycznie instalowane ani uruchamiane przez synchronizator.

## Zakres potwierdzenia

Mechanizm source lock, walidacja i checkout są objęte lokalnymi testami. Binarne wydanie Android nie jest rezultatem samego audytu repozytoriów. Bez kompletnego bootstrap i weryfikacji na urządzeniu projekt pozostaje pakietem źródłowym.

## Zintegrowany katalog aplikacji

Rejestr `config/upstreams.lock.json` zawiera obecnie 14 źródeł, w tym Node.js, xterm.js i Actions Runner. Wbudowany katalog aplikacji (`android/app/src/main/assets/upstream-catalog.js`) pokazuje przypięte commity i licencje offline. Pakiet backendu zawiera niezależny moduł `omega_actions.ultimate.upstream_sources` do bezpiecznego checkoutu, weryfikacji SHA i licencji. Opis API oraz testów: [UPSTREAM_SOURCE_INTEGRATION.md](UPSTREAM_SOURCE_INTEGRATION.md).
