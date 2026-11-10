"""Generate source-grounded engineering documentation from verified local artifacts."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import re
import textwrap

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend/omega_actions'
BENCH=json.loads((ROOT/'validation/simulation_benchmarks_v1.json').read_text())
NOM=BENCH['cases']['nominal_5000']; OUT=BENCH['cases']['outage_1000']


def write(name:str,content:str):
    (ROOT/name).write_text(textwrap.dedent(content).strip()+'\n',encoding='utf-8')


write('README.md', '''
# OMEGA Studio Android — izolowany pakiet źródeł, silnika CI i APK podglądowego

**Wydanie pakietu:** 1.0.0 · **interfejs APK:** 4.0.0 offline preview · **język:** polski · **tryb dostawy:** PACKAGE-ONLY.

Pakiet łączy rzeczywiste źródła natywnej aplikacji Android, działający i testowany lokalnie
silnik CI/CD Python, moduły GitHub i OpenAI API z polityką jawnych zgód, analizę GGUF,
pobieranie Hugging Face, deterministyczny symulator zależności zewnętrznych,
autoryzowane kontrakty przyszłego połączenia z Digital-Life i kompletne logi weryfikacyjne.

## Dostarczone artefakty

- `dist/OMEGA_STUDIO_ANDROID_OFFLINE_PREVIEW_v4.0.0.apk`: podpisany APK v2 z polskim edytorem offline,
  podglądem GGUF, formularzami ustawień i wywołaniem powłoki `/system/bin/sh`. Ten plik **nie zawiera**
  binarnego Termux, Python, Git, llama.cpp ani natywnego mostu API z folderu `android/`.
- `android/`: niezależne źródła Java, Gradle, HTML/CSS/JS z implementacją SAF, Android Keystore,
  GitHub REST read-only, pobieraniem Hugging Face, instalatorem bootstrap Termux i adapterem llama.cpp.
  Te źródła **nie zostały skompilowane pełnym Android SDK**.
- `backend/`: lokalny silnik Python (DAG/matrix, kontrola wykonania, artefakty, API REST/SSE,
  adaptery AI/GitHub, GGUF i odporność na awarie), łącznie z testami.
- `validation/`: realne wyniki uruchomień, benchmarki symulacyjne, testy przeglądarki i struktury APK.
- `tools/`: generowanie dokumentacji, walidacja i powtarzalne pakowanie.

## Lokalny start silnika Python (Linux/macOS/Windows)

Wymagane Python >= 3.11 i zależności z `backend/pyproject.toml`. Instalacja z sieci nie jest
wymagana, jeżeli zależności znajdują się już w środowisku. Przykład:

```bash
cd backend
python -m pip install -e .
OMEGA_ACTIONS_HOME="$HOME/.omega-actions" python -m omega_actions serve --host 127.0.0.1 --port 8765
```

Panel działa wyłącznie przy uruchomionym procesie Python. **Nie** jest to backend wbudowany w APK.
Wersja offline APK nie odwołuje się do `127.0.0.1:8765`.

```bash
cd backend
PYTHONPATH=. python -m omega_actions digital-twin --seed 20261110 --jobs 5000 --workers 8 --failure-rate 0.15
PYTHONPATH=. python -m omega_actions audit-verify
PYTHONPATH=. pytest -q tests
```

## Granice bezpieczeństwa

Dostęp do lokalnego API wymaga losowego `X-OMEGA-Token`; GitHub zapis jest domyślnie wyłączony.
Płatne API OpenAI wymaga osobnego klucza i włączenia przez operatora. Subskrypcja ChatGPT
nie jest kluczem API. W tym wydaniu nie wykonano zapisów w żadnym repozytorium,
nie uruchomiono GitHub-hosted Actions i nie przeprowadzono wdrożenia.

## Interpretacja wyników

Testy CPU/Chromium/Java-stub i deterministyczny digital twin nie potwierdzają działania
Termux w APK, pełnej kompilacji Gradle, fizycznego Androida ani usług zewnętrznych.
Ocena gotowości znajduje się w `PRODUCTION_READINESS_REPORT.md`.
''')

write('ARCHITECTURE.md', '''
# Architektura i granice procesów

```text
APK offline preview ── WebView assets ── JavaScript ── /system/bin/sh (lokalnie)
        │ (brak osadzonego Python runtime)
        └── niezależny projekt źródłowy Android (nie skompilowany pełnym SDK)
                 ├── NativeBridge / SAF / workspace / Android Keystore
                 ├── TermuxBootstrapInstaller (wymaga zgodnego archiwum)
                 └── GGUF / HF / GitHub read-only / llama.cpp adapter

Python runtime (oddzielny proces, opcjonalny localhost:8765)
        ├── FastAPI + CSRF session token + SSE
        ├── Engine ── DAG compiler ── scheduler ── runner (native / Docker)
        ├── GitHub REST ── policy ── owner approval ── tool gateway
        ├── OpenAI Responses API (domyślnie wyłączone)
        ├── GGUF inspector ── HF downloader ── llama.cpp adapter
        ├── SQLite WAL state + durable lease queue
        ├── HMAC audit chain + bounded latency telemetry
        └── Digital-Life signed exchange + migration journal (bez I/O do repo)

Deterministic simulation harness (offline)
        └── event queue + seeded faults + circuit breaker + bounded retries
```

## Podział odpowiedzialności

**Warstwa interfejsu:** `android/app/src/main/assets`, `omega_actions/static`, `api.py`.
**Sterowanie:** `compiler.py`, `engine.py`, `scheduler.py`, `automation.py`.
**Wykonanie:** `runner.py`, `actions.py`, `services.py`, `act_bridge.py`.
**Dane:** `storage.py`, `cache.py`, `artifacts.py`, `recovery.py`, `audit_ledger.py`.
**Bezpieczeństwo:** `vault.py`, `redaction.py`, `dl_contract.py`, `dl_adapter.py`.
**AI i modele:** `agent_gateway.py`, `ai_bridge.py`, `model_studio.py`, `inference.py`.
**Obserwowalność:** `resilience.py` (`LatencyTelemetry`) oraz łańcuch HMAC w `audit_ledger.py`.
**Symulacja:** `digital_twin.py` i `simulator.py` (dwa odrębne poziomy: infrastruktura i workflow).

## Granice zaufania

1. GitHub i Hugging Face są źródłami niezaufanych danych; nie należy wykonywać pobranego kodu
   bez świadomego wyboru trybu uruchomienia. Dostęp API nie oznacza uprawnień do zapisu.
2. WebView z natywnym JS bridge jest powierzchnią ataku; dostępna w APK powłoka systemowa
   może uruchamiać polecenia z uprawnieniami aplikacji. APK jest dystrybucją testową.
3. Lokalne API wymaga tokenu sesji i ogranicza hosty/origin. To nie jest publiczny serwer.
4. `SignedEnvelope` wymaga HMAC-SHA256, identyfikatora tenant, czasu życia, nonce i kontroli replay.
5. `MigrationJournal` zarządza wyłącznie lokalnymi metadanymi migracji; nie wykonuje integracji.

## Przepływ CI

YAML → walidacja i rozwinięcie matrix → DAG → scheduler EWMA CPU/RAM → workspace
→ wykonanie kroków → maskowanie sekretów → artefakty SHA-256 → SQLite state
→ wpis HMAC audit → telemetria. Ograniczenia natywnego wykonywania opisano w `SECURITY_ARCHITECTURE.md`.
''')

write('ENGINEERING_SPECIFICATION.md', '''
# Specyfikacja inżynieryjna i niezmienniki

## Retry, obwód awaryjny i obserwowalność

`RetryPolicy` stosuje ograniczoną liczbę prób `1 <= N <= 100`. Dla kolejnego opóźnienia
`i=0..N-2`:

\\[
 d_i = \\min(d_{max}, \\min(d_{max},d_0 2^i) \\cdot (1-J/2+J U_i)), \\quad U_i \\in [0,1).
\\]

`U_i` jest deterministycznie generowane przez `random.Random(seed)` w testach; produkcyjne
użycie nie powinno polegać na przewidywalności jittera jako zabezpieczeniu kryptograficznym.
`AdaptiveCircuitBreaker` implementuje `closed -> open -> half_open -> closed/open`,
z pojedynczą próbą w stanie half-open, zegarem monotonicznym i blokadą `threading.Lock`.
Nie jest to struktura lock-free ani twarda gwarancja czasu rzeczywistego.

`LatencyTelemetry` utrzymuje dla każdego klucza `deque(maxlen=capacity)` i licznik całkowity.
Percentyle liczone są metodą nearest-rank dla **próbek z okna**; pamięć jest ograniczona
przez `capacity` dla każdego klucza. Brak gwarancji sub-millisecond tail latency.

## Trwałość i integralność

`DurableLeaseQueue` wykorzystuje SQLite `BEGIN IMMEDIATE` do atomowego `claim` i `recover`.
Własność: `attempts <= max_attempts`; zakończenie wymaga aktualnego właściciela i
niewygasłej dzierżawy. Model jest **at-least-once**, a nie exactly-once dla efektów zewnętrznych.
Dla operacji z efektami ubocznymi odbiorca musi stosować klucz idempotencji.

Łańcuch audytu:

\\[
 h_i = \\operatorname{HMAC}_{SHA256}(K,\\operatorname{CanonicalJSON}(i,event,payload,t, h_{i-1})).
\\]

Klucz 256-bit jest generowany lokalnie z uprawnieniami 0600. Weryfikator wykrywa zmianę
zawartości i kolejności rekordów; bez zewnętrznego zakotwiczenia głowy łańcucha
nie wykryje usunięcia całej bazy i klucza przez napastnika z pełną kontrolą hosta.

## Kontrakt Digital-Life

Protokół `1.0`, kanoniczny JSON UTF-8, `tenant`, `kind`, `nonce` (128-bit),
`issued_at`, `expires_at`, `payload`, `signature` (HMAC-SHA256). `MAX_PAYLOAD=256 KiB`,
`MAX_TTL=600 s`; okno dopuszczalnego przesunięcia zegara 30 s. Anty-replay:
SQLite `UNIQUE(tenant,nonce)` i kontrola czasu ważności.

## Symulator

Ziarno determinuje losowanie opóźnień, awarii workerów i błędów sieci. Zdarzenia
`start/finish` uporządkowane są w kopcu `(czas,seq,typ,job)`. `worker_count` ogranicza
współbieżność; liczba prób wynosi maksymalnie 4, a budżet zdarzeń maksymalnie `30*jobs`.
Niezmienniki: brak podwójnego efektu, skończone retry, pusty backlog, bounded parallelism,
liczba odzyskanych dzierżaw nie większa od liczby awarii workerów.

## Ograniczenia wejścia

GGUF v2/v3: limit metadanych 8 MiB, do 100 000 kluczy, długość stringa do 1 MiB.
HF: do 50 GiB na model, kontrola hostów HTTPS, zakresów HTTP i opcjonalny SHA-256.
GitHub: walidowane `owner/name`, branch `omega/*`, jawne allowlisty i planowanie zmian.
Przyspieszenia GPU/NPU i realna przepustowość Android nie były mierzone.
''')

write('BEYOND_MAXIMUM_INNOVATIONS.md', f'''
# Zaimplementowane rozszerzenia inżynieryjne

Nazwa „Beyond-Maximum” identyfikuje warstwę funkcjonalną tego wydania; nie oznacza
udowodnionej przewagi nad wszystkimi rozwiązaniami rynkowymi. Poniższe pozycje mają
konkretne implementacje i lokalne testy.

| Rozszerzenie | Kod | Weryfikacja |
|---|---|---|
| Circuit breaker z jedną próbą half-open | `resilience.py:AdaptiveCircuitBreaker` | `test_omega_resilience_v1.py` |
| Retry exponential backoff z seedowanym jitterem | `resilience.py:RetryPolicy` | `test_omega_resilience_v1.py` |
| Bounded sliding-window percentiles | `resilience.py:LatencyTelemetry` | `test_omega_resilience_v1.py` |
| HMAC-SHA256 audyt transakcyjny | `audit_ledger.py:IntegrityLedger` | `test_omega_ledger_v1.py` |
| Wykrywanie tamper i atomowe zapisy wielowątkowe | `audit_ledger.py` | test 80 współbieżnych rekordów |
| SQLite leases, fencing i crash recovery | `recovery.py:DurableLeaseQueue` | `test_omega_recovery_v1.py` |
| Signed tenant-scoped contract + anti-replay | `dl_contract.py`, `dl_adapter.py` | `test_omega_contract_v1.py`, `test_omega_dl_adapter_v1.py` |
| Owner-controlled migracja z rollback | `dl_adapter.py:MigrationJournal` | `test_omega_dl_adapter_v1.py` |
| Digital twin z deterministycznym fault injection | `digital_twin.py` | `test_omega_twin_v1.py` |
| Automatyczny wpis audytu dla CI run | `engine.py` | `test_omega_engine_integration_v1.py` |
| Lokalne endpointy symulacji i telemetrii | `api.py` | `test_omega_engine_integration_v1.py` |

## Wynik pomiaru symulatora (lokalny CPU, nie Android)

- Scenariusz 5000 wirtualnych zadań / 8 workerów / 15% prawdopodobieństwa awarii sieci:
  **{NOM['measured_wall_ms']} ms czasu ściennego** i **{NOM['python_peak_alloc_bytes']} B szczytowych alokacji Python tracemalloc**.
- Scenariusz pełnego zaniku sieci 1000 zadań: **{OUT['measured_wall_ms']} ms czasu ściennego**.
- Wszystkie pięć niezmienników symulatora miało wynik `true` w obu scenariuszach.
- Wartości przepustowości i opóźnień z pola `virtual_results.metrics` opisują **czas symulowany**;
  nie są benchmarkiem Android, GitHub, Hugging Face, OpenAI ani llama.cpp.

## Granice twierdzeń

Nie zaimplementowano ani nie zmierzono lock-free/wait-free hot paths, GPU/NPU zero-copy,
formalnej weryfikacji Lean/Coq ani sprzętowej gwarancji opóźnień poniżej 1 ms.
Wymienione optymalizacje są konkretnymi, testowalnymi mechanizmami odporności i kontroli kosztów,
a nie certyfikacją jakości przewyższającej konkurencję.
''')

write('SECURITY_ARCHITECTURE.md', '''
# Architektura bezpieczeństwa i status audytu

## Threat model

Zasoby: lokalny workspace, tokeny GitHub/HF/OpenAI, repozytoria źródłowe,
artefakty CI, modele GGUF, wyniki Digital-Life. Atakujący: nieufny YAML, README,
model GGUF, odpowiedź API, skrypt CI, złośliwy WebView frame lub lokalny proces.

| Ryzyko | Kontrola w kodzie | Zakres dowodu |
|---|---|---|
| Prompt injection przez repo/LLM | agent tool allowlist, jawne plany, brak automatycznego wykonania | testy backendu |
| GitHub write bez zgody | `ActionController`, `write_enabled=False` domyślnie, TTL i allowlist | testy polityk |
| Przekroczenie tenant | `SignedEnvelope.verify(tenant=...)` | testy kontraktowe |
| Replay wiadomości | SQLite `ReplayGuard`, HMAC i nonce | testy anty-replay |
| Manipulacja historią audytu | HMAC chain, SQLite WAL | testy tamper |
| Wyciek tokenu | Android Keystore w źródłach, Python SecretVault, redaction | testy ograniczone do kodu |
| SSRF / złośliwy redirect HF | HTTPS allowlist, odrzucenie obcych hostów | mock transport |
| Path traversal | walidacja nazw modeli, workspace i ZIP bootstrap | testy jednostkowe / analiza źródeł |
| Worker crash / stale lease | atomowe lease fencing | testy recovery |
| DoS przez retry | bounded attempts, circuit breaker, max event budget | testy i symulacje |

## Krytyczna granica Android

APK offline preview zawiera JS bridge uruchamiający `/system/bin/sh`; nie zapewnia
konteneryzacji wykonywanych poleceń ani binarnego Termux. Źródła natywnego Android
nie są tym samym co binarny APK. Nie umieszczaj sekretów w poleceniach shell ani plikach
niezaufanego projektu. Lokalny backend `native` wykonuje skrypty z uprawnieniami
użytkownika; domyślnie wymaga świadomego włączenia.

## Status audytów

**EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE — WYŁĄCZNIE ADMINISTRACYJNE ZWOLNIENIE
PRZEZ WŁAŚCICIELA.** Rzeczywisty zewnętrzny audyt bezpieczeństwa i kryptografii:
**NOT PERFORMED**. Taka decyzja nie jest dowodem certyfikacji ani usunięcia ryzyk.

**SIMULATION ADMISSION: PASSED VIA DETERMINISTIC ENGINEERING SIMULATION** dla pięciu
ściśle zdefiniowanych niezmienników w `digital_twin.py`. Nie oznacza to
`DEPLOYED` ani `PRODUCTION_VERIFIED` dla systemów zewnętrznych.

## Model uprawnień

Zapis do repozytoriów nie jest wykonywany podczas budowania pakietu.
Integracja z ChatGPT przez OpenAI API nie jest równoznaczna z przekazaniem asystentowi
pełnych praw administratora GitHub. Narzędzia agentowe wymagają zakresów i zatwierdzeń.
''')

write('BUILD_AND_DEPLOYMENT_GUIDE.md', '''
# Budowanie, uruchamianie i polityka wydania

## Powtarzalna weryfikacja źródeł

```bash
cd backend
PYTHONPATH=. pytest -q tests
cd ..
node --test tests/test_ui.mjs
python tools/verify_android_sources.py
python tools/build_embedded_apk.py dist/OMEGA_STUDIO_ANDROID_OFFLINE_PREVIEW_v4.0.0.apk
python tools/validate_dex.py dist/OMEGA_STUDIO_ANDROID_OFFLINE_PREVIEW_v4.0.0.apk
python tools/run_benchmarks_v1.py
```

`verify_android_sources.py` kompiluje Java 17 przeciw lokalnym stubom Android API;
nie jest to kompilacja Android SDK. `build_embedded_apk.py` wytwarza niezależny,
mały podgląd APK DEX 035, a nie Gradle build źródeł natywnych.

## Natywny projekt Android

Katalog `android/` zawiera Gradle `com.android.application`, `compileSdk=35`,
`minSdk=26`, `targetSdk=28`. Pełna kompilacja wymaga Android SDK 35, narzędzi
budowania, zgodnych zależności i podpisania własnym kluczem. Polecenie w środowisku
z Gradle i Android SDK:

```bash
cd android
gradle :app:assembleDebug
```

W bieżącym odizolowanym środowisku nie było Android SDK/NDK ani pełnego toolchainu
Gradle; tego polecenia nie przedstawia się jako wykonanego. Zgodny bootstrap Termux
musi być skompilowany dla faktycznego `applicationId` i poprawnej architektury;
instalator sprawdza zadeklarowany prefix i SHA-256. Nie można bezpiecznie użyć
bootstrap przeznaczonego dla `com.termux` w aplikacji `org.omega.actions`.

## Lokalny backend

`python -m omega_actions serve --host 127.0.0.1 --port 8765` uruchamia proces lokalny.
Tryb `auto` preferuje ograniczone wykonanie, a `native` może uruchamiać kod z
uprawnieniami użytkownika. Płatne API jest wyłączone domyślnie.

## Wydanie i archiwizacja

`tools/build_package_v1.py` tworzy manifest SHA-256 dla wszystkich plików poza
samym manifestem i podpisaną paczkę ZIP (integralność ZIP/CRC, bez podpisu
wydawcy zewnętrznego). Nie jest wykonywane wdrożenie, commit, push ani release.
''')

write('TESTING_AND_VALIDATION.md', f'''
# Testy, symulacje i wyniki lokalne

| Obszar | Dowód | Wynik |
|---|---|---|
| Backend Python (pełna regresja) | `validation/python_full_v1.log` | **88 PASS, 4 subtests PASS, 0 FAIL** |
| JavaScript Node | `validation/node_full_v1.log` | **6 PASS, 0 FAIL** |
| Java 17 native core | `validation/native_core_v1.log` | **NATIVE_CORE_TEST_PASS** |
| Java 17 ze stubami Android | `validation/java_sources_v1.log` | **6 plików Java, PASS** |
| Browser Chromium headless | `validation/browser_v1.log` | **9 kontroli, 0 page errors** |
| APK v2 / DEX | `validation/apk_build_v1.json`, `validation/dex_v1.json` | **PASS, struktura i podpis** |
| Deterministyczny twin | `validation/simulation_benchmarks_v1.json` | **5/5 niezmienników dla 3 scenariuszy** |

## Test-driven development

`validation/tdd_v1_red.log`, `validation/tdd_engine_red.log`,
`validation/tdd_dl_red.log` dokumentują reprodukcję nieistniejących funkcji;
logi `tdd_*green*` dokumentują ich implementację i zaliczenie.

## Wirtualne środowisko awaryjne

Nominalny przebieg: seed `20261110`, `jobs=5000`, `workers=8`, `failure_rate=0.15`.
Wynik: **{NOM['virtual_results']['outcomes']['success']} sukcesów,
{NOM['virtual_results']['outcomes']['failure']} terminalnych błędów** (polityka
fail-closed, w tym odmowy przez circuit breaker),
**{NOM['virtual_results']['faults']['worker_crashes']} awarii workerów** i
**{NOM['virtual_results']['faults']['network_failures']} błędów sieci**.
To wstrzyknięte zdarzenia, nie obserwacje rzeczywistych usług.

Awaria całkowita: `jobs=1000`, `failure_rate=1.0`,
**{OUT['virtual_results']['outcomes']['failure']} terminalnych błędów**,
wszystkie niezmienniki `true`, brak nieskończonej pętli retry.

Pomiar ścienny CPU symulatora: **{NOM['measured_wall_ms']} ms** dla 5000 zadań,
**{OUT['measured_wall_ms']} ms** dla 1000 zadań podczas symulowanej awarii.
Brak porównania do konkurencji i brak gwarancji wydajności na telefonie.

## Ograniczenie epistemiczne

Nie wykonano Android SDK/Gradle release build, E2E na fizycznym Androidzie,
pobierania dużego GGUF przez publiczne HF ani inferencji na NPU/GPU.
Symulator nie zastępuje tych obserwacji. Administracyjny wyjątek od audytu
nie jest rzeczywistym zewnętrznym audytem.
''')

write('DEPENDENCIES_AND_LICENSES.md', '''
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
''')

write('DIGITAL_LIFE_COMPATIBILITY.md', '''
# Digital-Life: zgodność kontraktowa bez integracji

Źródło referencyjne: `mojealterego/Digital-Life`, `README.md` z 2026-11-09,
odczytane bez modyfikacji. Repozytorium opisuje NOEVARIS Ω jako jeden silnik
`IntegratedEngine`, z rozróżnieniem `PRODUCTION_ADMISSION_SIMULATED_ONLY`
od `DEPLOYED` i `PRODUCTION_VERIFIED`. Niniejszy pakiet jest **osobnym artefaktem
przygotowawczym**, nie nowym silnikiem wewnątrz Digital-Life.

## Implementowany kontrakt wymiany

`omega_actions.dl_contract.SignedEnvelope` v1.0 + `ReplayGuard` +
`omega_actions.dl_adapter.DigitalLifeAdapter`:

| Pole | Reguła |
|---|---|
| `version` | `1.0` |
| `tenant` | wymagany identyfikator izolacji |
| `kind` | `omega.studio.exchange.v1` |
| `nonce` | 128-bit hex, unikalny w tenant |
| `issued_at`, `expires_at` | sekundy Unix, TTL maks. 600 s |
| `payload` | max 256 KiB kanonicznego JSON |
| `signature` | HMAC-SHA256 z kluczem właściciela |

Dozwolone możliwości: `ci.request`, `ci.result`, `model.metadata`, `research.summary`.
`DigitalLifeAdapter` odrzuca inne capability, w tym próby `repo.push`.

## Mapa odpowiedzialności

| OMEGA Studio | Potencjalny odbiorca Digital-Life | Granica |
|---|---|---|
| CI result / workflow metadata | warstwa lokalnych zadań | tylko zweryfikowana wiadomość |
| GGUF metadata + SHA-256 | katalog lokalnych modeli | bez wykonywania modelu |
| Research summary digest | indeks wiedzy | digest, nie dowód matematyczny |
| HMAC audit head | archiwum pochodzenia | wymaga odrębnego zaufanego zakotwiczenia |

## Kontrola konfliktów

Brak współdzielenia katalogów runtime, plików stanu i bazy SQLite. Adapter
nie importuje modułów `IntegratedEngine` i nie ingeruje w jego roadmapę.
Migracja jest reprezentowana lokalnym `MigrationJournal`, bez sieci i zapisu do repo.
Testy symulują zgodność formatu i stanu, nie potwierdzają interoperacyjności
z rzeczywistą wersją Digital-Life ani podpisaną migracją produkcyjną.
''')

write('INTEGRATION_BLUEPRINT.md', '''
# Blueprint przyszłej integracji — dokument kontraktu, bez operacji na repo

## Wariant logiczny

`OMEGA Studio -> SignedEnvelope -> policy gateway -> Digital-Life LocalRuntime`.
Brama powinna akceptować tylko zgodne wersje i allowlistę capability, sprawdzać
HMAC, nonce, TTL, tenant i identyfikator zadania. Po stronie Digital-Life
wymagana jest niezależna implementacja weryfikatora tego samego kontraktu.

## Stany migracji (zaimplementowane lokalnie)

`planned -> shadow -> approved -> active -> rolled_back`.

- `planned`: zapis digestu artefaktu i wersji protokołów w SQLite.
- `shadow`: porównanie kontraktów bez przełączenia produkcyjnych odbiorców.
- `approved`: HMAC token właściciela związany z profilem, wersjami i SHA-256.
- `active`: przejście stanu metadanych, **nie** automatyczne wdrożenie.
- `rolled_back`: deterministyczna blokada ponownej aktywacji tego profilu.

Każda zmiana stanu jest atomowa w SQLite. Błędna kolejność lub nieprawidłowy
podpis powodują odmowę. Aktywacja nie wykonuje `git push`, `merge`, migracji
zewnętrznej bazy ani wywołania produkcyjnego API.

## Przykładowa wymiana

```python
from pathlib import Path
from omega_actions.dl_adapter import DigitalLifeAdapter
adapter = DigitalLifeAdapter('tenant-a', key=b'K'*32, replay_path=Path('replay.db'))
envelope = adapter.encode('ci.result', {'run_id':'r1','status':'success'})
assert adapter.decode(envelope)['data']['status'] == 'success'
```

Przykład używa demonstracyjnego klucza i lokalnej bazy; nie nadaje się jako
sekret produkcyjny. Rejestr anty-replay odrzuci powtórne przetworzenie.

## Semantyka API

`ci.request` przekazuje nazwę workflow i workspace; nie jest zgodą na wykonanie
niezaufanego kodu. `ci.result` zawiera tylko identyfikator i status.
`model.metadata` zawiera nazwę, SHA-256 i format `gguf`.
`research.summary` przenosi temat i digest. Każde rozszerzenie capability
wymaga nowej, jawnie wersjonowanej polityki po obu stronach.
''')

write('PRODUCTION_READINESS_REPORT.md', '''
# Raport gotowości i rozliczenie kryteriów

**STATUS: LOCAL SOURCE VALIDATED + OFFLINE APK PREVIEW BUILT.**

Nie istnieją dowody pozwalające rzetelnie nadać status
`100% PRODUCTION READY — BEYOND-MAXIMUM TIER` dla kompletnej aplikacji Android.
Weryfikacja źródeł i symulacji nie jest równoważna pełnemu Android SDK build,
Termux bootstrap, inferencji na telefonie ani testom usług rzeczywistych.

| Kryterium | Dowód i wynik |
|---|---|
| Odizolowany katalog projektu | `OMEGA_STUDIO_ANDROID_PACKAGE_v1/` — TAK |
| Źródła Python, Java, JS, HTML, CSS | W pakiecie — TAK |
| 13 dokumentów inżynieryjnych | Katalog główny — TAK |
| Python regresja | 88 PASS + 4 subtests |
| JS | 6 PASS |
| Java native core i stub compile | PASS |
| APK offline preview + podpis v2 | PASS strukturalny |
| Deterministyczne symulacje zewnętrznych zależności | 5/5 niezmienników PASS w 3 scenariuszach |
| Integracja z prawdziwym Digital-Life | Nie wykonana, zgodnie z zakazem |
| Wpisy do istniejących repozytoriów | Brak |
| Zewnętrzny audyt | Zwolnienie administracyjne, nie wykonano audytu |
| Samodzielne Termux/Python/Git/llama.cpp w APK | Brak w binarnym podglądzie |
| Fizyczny Android / Gradle SDK E2E | Brak pomiaru |

**EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE** — etykieta decyzji właściciela
w zakresie administracyjnego zwolnienia z audytu; rzeczywisty status audytu
zewnętrznego: **NOT PERFORMED**. Nie jest to atestacja bezpieczeństwa.

**EXTERNAL ARCHITECTURE SIMULATION: PASSED VIA DETERMINISTIC ENGINEERING SIMULATION**
w zakresie pięciu jawnych niezmienników modelu dyskretno-zdarzeniowego.
Wynik nie potwierdza produkcyjnego wdrożenia ani dostępności usług.

**Repozytorium Digital-Life: READ-ONLY, bez commit/push/PR, bez wdrożenia.**
''')

# Source-derived complete Python module index
entries=[]
for path in sorted(BACKEND.glob('*.py')):
    tree=ast.parse(path.read_text('utf-8'))
    funcs=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            funcs.append(('async ' if isinstance(node,ast.AsyncFunctionDef) else '')+node.name+'('+', '.join(a.arg for a in node.args.args)+')')
        if isinstance(node,ast.ClassDef):
            methods=[x.name for x in node.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
            funcs.append(node.name+' {'+', '.join(methods)+'}')
    doc=ast.get_docstring(tree) or 'Moduł implementacyjny silnika.'
    entries.append(f"### `{path.name}`\n\n{doc.strip().splitlines()[0]}\n\n"+('\n'.join(f'- `{f}`' for f in funcs) if funcs else 'Eksporty modułu przez importy i konfigurację.')+'\n')
write('MODULE_REFERENCE.md','# Referencja modułów i funkcji\n\nWygenerowano z AST rzeczywistych plików `backend/omega_actions/*.py`.\nKażdy nagłówek odpowiada istniejącemu modułowi; funkcje są indeksowane według nazw.\n\n'+'\n'.join(entries))

# Source-derived FastAPI endpoints
api=ast.parse((BACKEND/'api.py').read_text('utf-8'))
endpoint_rows=[]
for node in ast.walk(api):
    if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        continue
    for deco in node.decorator_list:
        if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and isinstance(deco.func.value,ast.Name) and deco.func.value.id=='app':
            if deco.args and isinstance(deco.args[0],ast.Constant):
                endpoint_rows.append((deco.func.attr.upper(),deco.args[0].value,node.name))
endpoint_rows.sort(key=lambda r:(r[1],r[0]))
api_table='\n'.join(f'| `{method}` | `{route}` | `{fn}` |' for method,route,fn in endpoint_rows)
write('API_REFERENCE.md',f'''
# Referencja interfejsów

## Lokalne HTTP REST (źródło `api.py`)

Bazowy adres: `http://127.0.0.1:8765`. Każdy `/api/*` wymaga
`X-OMEGA-Token: <token sesji>` i kontroli Origin. Token jest losowany
przy uruchomieniu procesu; nie jest publicznym kluczem API. Domyślnie
wyłączone są zapisy do GitHub i płatne wywołania OpenAI.

| Metoda | Ścieżka | Funkcja |
|---|---|---|
{api_table}

### `/api/omega/simulation`

`POST` JSON: `{{"seed":20261110,"jobs":500,"workers":4,"failure_rate":0.15}}`.
`jobs` w zakresie 1..10000, `workers` 1..64, `failure_rate` 0..1.
Odpowiedź: `scope`, `outcomes`, `faults`, `metrics`, `invariants`, `simulated_components`.
Wywołanie nie dotyka sieci ani Digital-Life.

### `/api/omega/telemetry`

`GET`: `ci_run` (bounded latency stats), `audit_head` (HMAC chain verification),
`scope=LOCAL_RUNTIME_ONLY`. Błąd integralności łańcucha blokuje poprawny wynik.

## CLI

`omega-actions validate`, `run`, `serve`, `simulate`, `act`, `watch`, `hook`, `vault`,
`digital-twin`, `audit-verify`, `recover-interrupted`.

`omega-models inspect`, `download`, `toolchains` (szczegóły w `model_cli.py`).

## Kontrakt Digital-Life

`SignedEnvelope.issue(tenant,kind,payload,key,now,ttl,nonce)`;
`SignedEnvelope.verify(envelope,key,now,tenant,replay_guard)`;
`DigitalLifeAdapter.encode/decode` i `MigrationJournal.plan/start_shadow/approve/activate/rollback`.
Komunikaty są podpisywane HMAC-SHA256; szczegóły w `DIGITAL_LIFE_COMPATIBILITY.md`.
''')
print(json.dumps({'root_markdown_files':len(list(ROOT.glob('*.md'))),
                  'python_modules':len(entries),'http_endpoints':len(endpoint_rows)},indent=2))
