# Referencja interfejsów

## Lokalne HTTP REST (źródło `api.py`)

Bazowy adres: `http://127.0.0.1:8765`. Każdy `/api/*` wymaga
`X-OMEGA-Token: <token sesji>` i kontroli Origin. Token jest losowany
przy uruchomieniu procesu; nie jest publicznym kluczem API. Domyślnie
wyłączone są zapisy do GitHub i płatne wywołania OpenAI.

| Metoda | Ścieżka | Funkcja |
|---|---|---|
| `GET` | `/` | `index` |
| `GET` | `/api/artifacts/{run_id}/{name}` | `artifact` |
| `GET` | `/api/billing` | `billing` |
| `POST` | `/api/compile` | `compile_endpoint` |
| `GET` | `/api/health` | `health` |
| `GET` | `/api/models` | `models` |
| `POST` | `/api/models/hf/download` | `download_hf_model` |
| `GET` | `/api/models/parameters` | `model_parameters` |
| `POST` | `/api/models/parameters` | `save_model_parameters` |
| `GET` | `/api/models/{name}` | `model_info` |
| `POST` | `/api/omega/agent/run` | `omega_agent` |
| `POST` | `/api/omega/chat` | `omega_chat` |
| `POST` | `/api/omega/compatibility` | `omega_compatibility` |
| `GET` | `/api/omega/github/repos` | `omega_repos` |
| `GET` | `/api/omega/github/workflows` | `omega_github_workflows` |
| `POST` | `/api/omega/mcp` | `omega_mcp` |
| `POST` | `/api/omega/oauth/poll` | `omega_oauth_poll` |
| `POST` | `/api/omega/oauth/start` | `omega_oauth_start` |
| `GET` | `/api/omega/plans` | `omega_plans` |
| `POST` | `/api/omega/plans` | `omega_propose` |
| `POST` | `/api/omega/plans/{plan_id}/approve` | `omega_approve` |
| `POST` | `/api/omega/plans/{plan_id}/execute` | `omega_execute` |
| `POST` | `/api/omega/simulation` | `simulation_endpoint` |
| `GET` | `/api/omega/status` | `omega_status` |
| `GET` | `/api/omega/telemetry` | `telemetry_endpoint` |
| `GET` | `/api/runs` | `list_runs` |
| `POST` | `/api/runs` | `run_endpoint` |
| `GET` | `/api/runs/{run_id}` | `get_run` |
| `POST` | `/api/runs/{run_id}/cancel` | `cancel` |
| `GET` | `/api/runs/{run_id}/events` | `events` |
| `POST` | `/api/runs/{run_id}/rerun` | `rerun` |
| `GET` | `/api/secrets` | `secret_names` |
| `POST` | `/api/secrets` | `save_secret` |
| `GET` | `/api/workflows` | `workflows` |
| `GET` | `/mobile` | `mobile` |
| `MIDDLEWARE` | `http` | `guard` |

### `/api/omega/simulation`

`POST` JSON: `{"seed":20261110,"jobs":500,"workers":4,"failure_rate":0.15}`.
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

## REST API v1.1

`GET /api/providers` — lista dostawców i status polityki kosztowej. Wymaga `X-OMEGA-Token`.

`POST /api/providers/chat` — JSON: `provider` (ID katalogu), `model`, `message`, `max_tokens` (1–4096), `confirm_cost` (boolean). Wymaga tokenu sesji, klucza z szyfrowanego vault oraz ustawienia `OMEGA_ENABLE_PAID_AI=true` dla zewnętrznych usług. Odpowiedź: `provider`, `model`, `text`, `usage`. Odpowiedzi błędne: 401, 422, 503.

Android JS bridge: `chatProvider(provider,model,message,confirmCost,callbackId)`, `runWorkflow(filename,confirmUnsafe,callbackId)`, `installBootstrap(callbackId)`, `providerCatalog()`. Te metody znajdują się w źródłach natywnych; nie występują w minimalnym DEX podglądowym.
