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

## Kontrole dodane v1.1

- Tokeny są przechowywane w Android Keystore AES-GCM (źródła natywne) albo w szyfrowanym `SecretVault` (backend Python).
- Provider HTTPS jest wybierany z zamkniętej listy, nie z nieufnego adresu; lokalne serwery mają przypięty loopback.
- Koszt zewnętrznego API wymaga jawnego potwierdzenia. W backendzie dodatkowo obowiązuje `OMEGA_ENABLE_PAID_AI`.
- Bramka wydania odrzuca brak binariów zamiast zastępować je atrapą.
- Testy z transportem `httpx.MockTransport` nie zastępują testów na żywych kontach.

**EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE** — wyłącznie administracyjne odstąpienie, nie wykonanie audytu. Nie oznacza certyfikacji.
