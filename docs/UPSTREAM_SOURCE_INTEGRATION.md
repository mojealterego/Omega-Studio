# OMEGA Studio — integracja oficjalnych projektów open source

## Źródła, wersjonowanie i pochodzenie

`config/upstream_sources.lock.json` przypina 14 oficjalnych projektów do pełnych 40-znakowych SHA commitów. Źródła z GitHub są pobierane przez Git bez uruchamiania ich kodu i bez instalowania nieznanych skryptów. Dla Code-OSS zachowana jest konkretna wersja **1.85.1** (commit `0ee08df0cf4527e40edc9aa28f4b5bd38bbff2b2`). Pozostałe źródła są przypięte do commitów ustalonych podczas przeglądu z 10.11.2026, a nie do ruchomych gałęzi.

| Projekt | Rola | Licencja zadeklarowana w repozytorium | Sposób wykorzystania |
|---|---|---|---|
| `termux/termux-app` | aplikacja Android/terminal | GPL-3.0-only | odniesienie do terminala, instalatora, interfejsów i izolacji procesu |
| `termux/termux-packages` | budowa ARM64/Bionic | licencje zależne od pakietu | budowanie pakietów dla `org.omega.actions` i właściwego `$PREFIX` |
| `coder/code-server` | IDE w przeglądarce | MIT | edytor, serwer, kompatybilne rozszerzenia |
| `microsoft/vscode` | Code-OSS 1.85.1 | MIT (kod źródłowy) | bazowe funkcje edytora i protokoły rozszerzeń; bez marki/binariów Microsoft VS Code |
| `ggml-org/llama.cpp` | lokalne GGUF | MIT | kompilacja `llama-cli` i silnika lokalnej inferencji |
| `git/git` | system kontroli wersji | GPL-2.0-only | natywne polecenie Git i integracja IDE |
| `python/cpython` | interpreter | PSF-2.0 | Python ARM64/Bionic i backend CI/CD |
| `nodejs/node` | runtime | MIT i licencje komponentów | Node.js dla code-server |
| `microsoft/monaco-editor` | edytor webowy | MIT | IntelliSense / edycja / podświetlanie (wymaga rzeczywistej integracji dystrybucji) |
| `xtermjs/xterm.js` | terminal webowy | MIT | interfejs terminala (wymaga rzeczywistej integracji dystrybucji) |
| `actions/runner` | CI/CD | MIT | źródło implementacji protokołów runnera, nie gwarancja pełnej zgodności Actions |
| `cli/cli` | integracja GitHub CLI | MIT | klient GitHub i operacje na repozytoriach |
| `tree-sitter/tree-sitter` | parser kodu | MIT | parsowanie inkrementalne, AST i języki |
| `huggingface/huggingface_hub` | repozytoria modeli | Apache-2.0 | integracja katalogu i pobierania modeli |

**Publiczny kod źródłowy nie oznacza dowolnego prawa do kopiowania lub dystrybucji binariów.** GPL-2.0-only i GPL-3.0-only mają obowiązki udostępnienia odpowiednich źródeł i not licencyjnych. Zależności w pakietach Termux posiadają odrębne licencje. Microsoft Visual Studio Code jako gotowy produkt nie jest tożsamy z kodem Code-OSS na licencji MIT. GitHub jako usługa nie jest w całości projektem open source; open-source jest między innymi `actions/runner`.

## Pobranie źródeł i kontrola integralności

```bash
python3 tools/sync_upstream_sources.py list
mkdir -p upstream-sources
python3 tools/sync_upstream_sources.py --root upstream-sources sync termux-packages --consent
python3 tools/sync_upstream_sources.py --root upstream-sources verify termux-packages
```

Pobranie wszystkich 14 projektów, z pełną świadomością zużycia dysku i sieci:

```bash
python3 tools/sync_upstream_sources.py --root upstream-sources sync all --consent
```

Manager waliduje dozwolone hosty HTTPS, pełne SHA, pliki licencyjne, stan Git, symlinki i lokalizację katalogu. Wyniki zapisuje w `upstream-sources/.omega-provenance/*.json`. Nie pobiera źródeł automatycznie. API `GET /api/ultimate/upstreams` pokazuje katalog, a `POST /api/ultimate/upstreams/sync` pobiera wskazany projekt wyłącznie z jawną flagą `confirm_network=true`, przy autoryzacji `X-OMEGA-Token`. Interfejs wymaga zaznaczenia zgody na licencję i pobieranie.

## Rzeczywiste wykorzystanie do APK

Źródła są wejściem do oddzielnych procesów budowania. `tools/build_custom_termux.sh` buduje dla `/data/data/org.omega.actions/files/usr`, a `tools/runtime_supply_chain.py` weryfikuje i pakuje prawdziwe pliki ELF Android ARM64. `tools/verify_runtime_bundle.py` wymaga `bash`, `python`, `git`, `llama-cli`, `node`, `code-server` i zasobów edytora. `tools/build_full_apk.sh` zatrzymuje się, gdy brakuje binariów lub Android SDK i fizycznego testu.

Samo pobranie repozytoriów **nie oznacza skompilowania ani dołączenia programów do APK**. Prawidłowy build wymaga narzędzi Android SDK/NDK, kompilatora i zasobów Termux oraz prawidłowego zarządzania licencjami. W obecnym środowisku sieć Git i Android SDK nie są dostępne; testy źródeł odbyły się na lokalnym repozytorium Git z rzeczywistym checkoutem przypiętego commita.

## Zagrożenia i zabezpieczenia

- Odmowa `http://`, `ssh://`, `file://` (poza wstrzykiwanym trybem testowym), dowolnych hostów, portów i URL z poświadczeniami.
- Brak uruchamiania pobranych skryptów i automatycznego budowania cudzych repozytoriów.
- `git` bez hooków, submodułów i interaktywnego pobierania poświadczeń.
- Brak nadpisywania istniejącego checkoutu; osobny katalog źródeł, blokada międzyprocesowa i pochodzenie SHA/licencji.
- Ochrona przed ścieżkami względnymi, symlinkami wychodzącymi poza checkout i podmienionymi licencjami.
- Pobieranie źródeł jest operacją sieciową; opłaty za transmisję, dysk i ewentualne usługi nie są automatycznie zerowe.

## Weryfikacja

```bash
PYTHONPATH=.:backend pytest -q tests/ultimate/test_upstream_sources.py
PYTHONPATH=.:backend python tools/test_ultimate_browser.py
```

Wyniki testów lokalnych potwierdzają zachowanie managera i UI, nie dowodzą kompatybilności skompilowanych binariów z fizycznym Androidem.
