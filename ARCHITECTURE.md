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

## Rozszerzenie v1.1

`Android WebView assets` → `NativeBridge` → `SecureVault`/`ProviderCatalog` → wybrane HTTPS API; klucze pozostają po stronie Java. `RuntimeAssetsInstaller` instaluje SHA-256-związane źródła backendu w katalogu prywatnym. `TermuxBootstrapInstaller` przyjmuje wyłącznie bootstrap skompilowany dla `org.omega.actions`. `runWorkflow` uruchamia `python -m omega_actions run` z listą argumentów bez interpolacji shell, wyłącznie po zgodzie użytkownika. Lokalny Python backend udostępnia niezależny, zabezpieczony tokenem API serwer FastAPI.
