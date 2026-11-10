"""Write truthful v1.1 engineering status and additive module documentation."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
status='''# OMEGA Studio Android — v1.1.0 / aktualny stan

**Zakres dostawy:** źródła Android/Java, kod silnika CI/CD Python, interfejs polski, testy, offline APK podglądowy i manifest SHA-256.

**Nie jest to samodzielny APK produkcyjny z Termux/Python/Git/llama.cpp.** Brak zgodnego bootstrap ARM64 z binariami, nie ma Android SDK/Gradle ani weryfikacji na urządzeniu. Bramka `tools/build_android_release.sh` celowo kończy się `BLOCKED` zamiast publikować pozornie kompletny produkt. Stary APK v4 nie jest nowym wydaniem natywnym.

**Nowe w v1.1:** 24 dostawców AI, opt-in kosztów, skarbiec Android Keystore, wielomodelowy chat w natywnych źródłach, backend `/api/providers` i `/api/providers/chat`, integralność bootstrap SHA-256/prefix/ELF, atomowy instalator kodu backendu, natywny kontroler workflow z wymaganą zgodą na wykonanie kodu, polski interfejs.

**Repozytorium Digital-Life:** tylko odczyt, zero modyfikacji, push/commit/PR i uruchomień GitHub Actions.

'''
readme=root/'README.md'
readme.write_text(status+readme.read_text('utf-8'),encoding='utf-8')
add={
'ARCHITECTURE.md':'''## Rozszerzenie v1.1

`Android WebView assets` → `NativeBridge` → `SecureVault`/`ProviderCatalog` → wybrane HTTPS API; klucze pozostają po stronie Java. `RuntimeAssetsInstaller` instaluje SHA-256-związane źródła backendu w katalogu prywatnym. `TermuxBootstrapInstaller` przyjmuje wyłącznie bootstrap skompilowany dla `org.omega.actions`. `runWorkflow` uruchamia `python -m omega_actions run` z listą argumentów bez interpolacji shell, wyłącznie po zgodzie użytkownika. Lokalny Python backend udostępnia niezależny, zabezpieczony tokenem API serwer FastAPI.
''',
'ENGINEERING_SPECIFICATION.md':'''## Inwarianty v1.1

1. Żaden zewnętrzny provider nie zostanie wywołany bez jednoczesnego `OMEGA_ENABLE_PAID_AI=true` oraz `confirm_cost=true` w backendzie.
2. URL dostawcy pochodzi z wbudowanego katalogu 24 usług; brak dowolnego adresu z żądania użytkownika; przekierowania HTTP nie są śledzone.
3. Token nie jest przekazywany do JS ani do URL query; w wynikach i błędach gateway nie zwraca nagłówków autoryzacji.
4. Bootstrap musi pasować do prefiksu `/data/data/org.omega.actions/files/usr`, SHA-256 i ELF `e_machine=183` dla wymaganych poleceń.
5. Źródła backendu są rozpakowywane po weryfikacji SHA-256, w prywatnym katalogu, z blokadą zip-slip i limitem rozmiaru.
6. Wykonywanie YAML wymaga zgody operatora i obecności Pythona/Git; nie ma zastępczego wykonania w systemowej powłoce.
''',
'BEYOND_MAXIMUM_INNOVATIONS.md':'''## Wdrożone zmiany v1.1 — zakres dowodów

- Katalog 24 endpointów z walidacją schematu, autoryzacją w nagłówkach i opt-in kosztów: `providers.py`, `ProviderCatalog.java`, testy `test_provider_gateway_v11.py`.
- Kontrola integralności pakietu ARM64 i powiązania z Android package ID: `tools/verify_runtime_bundle.py` + 7 testów.
- Deterministyczne, powtarzalne pakowanie źródeł Python z SHA-256: `tools/prepare_android_assets.py` + test.
- Weryfikowane rozpakowanie i uruchamianie workflow z ograniczeniami: `RuntimeAssetsInstaller.java`, `NativeBridge.java`.

Nie ma benchmarku porównawczego potwierdzającego przewagę nad GitHub Actions, VS Code lub Termux. Metryki symulacji są wirtualne, nie są pomiarem fizycznego urządzenia.
''',
'MODULE_REFERENCE.md':'''## Moduły dodane v1.1

- `omega_actions.providers.ProviderGateway.chat`: obsługa openai-compatible, Anthropic, Gemini, Ollama; limit odpowiedzi 1 MiB, timeout, bez redirect.
- `omega_actions.providers.list_providers/get_provider`: zamknięty katalog 24 endpointów.
- `ProviderCatalog.java`: walidowany katalog JSON z zasobów APK.
- `NativeBridge.chatProvider`: asynchroniczne zapytania do zewnętrznych modeli; token z Keystore.
- `NativeBridge.runWorkflow`: lokalne wykonanie wskazanego YAML, jawne uprawnienie do wykonania.
- `RuntimeAssetsInstaller`: atomowe rozpakowanie zweryfikowanego ZIP backendu.
- `tools.verify_runtime_bundle.inspect_runtime_bundle`: bramka integralności ARM64.
- `tools.prepare_android_assets.package_backend`: deterministyczny ZIP źródeł Python.
''',
'API_REFERENCE.md':'''## REST API v1.1

`GET /api/providers` — lista dostawców i status polityki kosztowej. Wymaga `X-OMEGA-Token`.

`POST /api/providers/chat` — JSON: `provider` (ID katalogu), `model`, `message`, `max_tokens` (1–4096), `confirm_cost` (boolean). Wymaga tokenu sesji, klucza z szyfrowanego vault oraz ustawienia `OMEGA_ENABLE_PAID_AI=true` dla zewnętrznych usług. Odpowiedź: `provider`, `model`, `text`, `usage`. Odpowiedzi błędne: 401, 422, 503.

Android JS bridge: `chatProvider(provider,model,message,confirmCost,callbackId)`, `runWorkflow(filename,confirmUnsafe,callbackId)`, `installBootstrap(callbackId)`, `providerCatalog()`. Te metody znajdują się w źródłach natywnych; nie występują w minimalnym DEX podglądowym.
''',
'SECURITY_ARCHITECTURE.md':'''## Kontrole dodane v1.1

- Tokeny są przechowywane w Android Keystore AES-GCM (źródła natywne) albo w szyfrowanym `SecretVault` (backend Python).
- Provider HTTPS jest wybierany z zamkniętej listy, nie z nieufnego adresu; lokalne serwery mają przypięty loopback.
- Koszt zewnętrznego API wymaga jawnego potwierdzenia. W backendzie dodatkowo obowiązuje `OMEGA_ENABLE_PAID_AI`.
- Bramka wydania odrzuca brak binariów zamiast zastępować je atrapą.
- Testy z transportem `httpx.MockTransport` nie zastępują testów na żywych kontach.

**EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE** — wyłącznie administracyjne odstąpienie, nie wykonanie audytu. Nie oznacza certyfikacji.
''',
'BUILD_AND_DEPLOYMENT_GUIDE.md':'''## Budowanie Android v1.1

Z katalogu głównego:

```bash
python3 tools/prepare_android_assets.py
python3 tools/verify_runtime_bundle.py
bash tools/build_android_release.sh
```

Bramka oczekuje `android/app/src/main/assets/bootstrap-aarch64-v8a.zip`, `bootstrap-aarch64-v8a.sha256`, `bootstrap-prefix.txt` z prawidłowym SHA, ELF AArch64 i prefiksem dla `org.omega.actions`, oraz lokalnego Android SDK/Gradle. Wymagane jest również poprawne środowisko Python z zależnościami dla backendu i natywne llama.cpp. Brak pakietów oznacza jawny błąd, nie budowę pozornego wydania.

`dist/OMEGA_STUDIO_ANDROID_UI_PREVIEW_v1.1.0.apk` to **podgląd** offline z minimalnym DEX. Nie zawiera natywnych klas z `android/app/src/main/java` ani binariów Termux, Python, Git i llama.cpp.
''',
'TESTING_AND_VALIDATION.md':'''## Regresja v1.1 (2026-11-10)

- `PYTHONPATH=backend:. pytest -q backend/tests tests`: **108 PASS, 4 podtesty PASS**, 0 FAILED.
- `node --test tests/test_ui.mjs`: **7 PASS**.
- `python tools/test_browser_ui.py`: **12 kontroli PASS**, 0 błędów JavaScript strony.
- `python tools/verify_android_sources.py`: kompilacja **8 plików Java** przeciwko stubom API — PASS, nie jest to kompilacja Android SDK.
- `python -m omega_actions digital-twin --seed 20261110 --jobs 5000 --workers 8 --failure-rate 0.15`: **5/5 niezmienników symulacji PASS**; 4151 sukcesów i 849 symulowanych błędów (awarie są częścią scenariusza).
- `tools/build_android_release.sh`: **BLOCKED**, brak bootstrap i Android SDK. Taki wynik jest prawidłowym zachowaniem fail-closed, nie zaliczeniem fizycznego APK.

Dowody: `validation/full_pytest_v11.log`, `validation/digital_twin_v11.json`, `validation/browser_ui.json`, `validation/android_release_gate.log`.
''',
'DEPENDENCIES_AND_LICENSES.md':'''## v1.1

Dodano `providers.py` (wykorzystuje istniejący `httpx`), `ProviderCatalog.java` i `RuntimeAssetsInstaller.java` (Java SDK/Android SDK), katalog JSON oraz kod interfejsu bez nowych bibliotek npm. Licencje zewnętrznych Termux/Python/Git/llama.cpp wymagają dołączenia odpowiednich tekstów licencyjnych w finalnej dystrybucji binarnej. Pakiet v1.1 nie dystrybuuje tych binariów.
''',
'DIGITAL_LIFE_COMPATIBILITY.md':'''## v1.1

Rozszerzenia Chat/API i runtime pozostają w osobnym katalogu projektu. Digital-Life nie było używane do testów wykonawczych. Dotychczasowe kontrakty `dl_contract.py`, `dl_adapter.py` i symulacja pozostają bez modyfikacji w repozytorium docelowym. Integracja GitHub pozostaje zgodna z polityką braku zapisów.
''',
'INTEGRATION_BLUEPRINT.md':'''## Granice integracji v1.1

Przyszłe połączenie może wykorzystać wyłącznie jawnie autoryzowane interfejsy CI oraz kontrakty wymiany zdarzeń. W obecnym pakiecie nie ma automatycznej synchronizacji, instalacji hooków, push/commit/PR ani modyfikacji Digital-Life. Zapis do GitHub pozostaje domyślnie wyłączony i podlega odrębnemu mechanizmowi zgód.
''',
'PRODUCTION_READINESS_REPORT.md':'''## Stan wydania v1.1

**SOURCE VALIDATED / ANDROID PRODUCTION BUILD BLOCKED**.

108 testów Python, 4 podtesty, 7 testów JS, 12 kontroli przeglądarkowych, kompilacja Java przeciwko stubom i 5 niezmienników symulacji: pozytywne. **Nie ma produkcyjnego APK z Termux, Python, Git, llama.cpp.** Bramka wydania zakończyła się kodem 2, ponieważ wymagany bootstrap nie został dostarczony. Nie ma dowodu fizycznego wykonania Android, niezależnego audytu, pełnego Gradle build ani testów prawdziwych usług API.

`EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE` to administracyjne zwolnienie, nie wynik rzeczywistego audytu. `PASSED VIA DETERMINISTIC ENGINEERING SIMULATION` dotyczy wyłącznie modelu symulacyjnego, nie rzeczywistej infrastruktury.

Repozytorium Digital-Life: bez zmian.
'''
}
for name,content in add.items():
    p=root/name
    text=p.read_text('utf-8')
    p.write_text(text.rstrip()+'\n\n'+content,encoding='utf-8')
print('updated',len(add)+1,'documents')
