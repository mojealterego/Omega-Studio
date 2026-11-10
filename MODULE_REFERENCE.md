# Referencja modułów i funkcji

Wygenerowano z AST rzeczywistych plików `backend/omega_actions/*.py`.
Każdy nagłówek odpowiada istniejącemu modułowi; funkcje są indeksowane według nazw.

### `__init__.py`

OMEGA Actions Local Engine: explicit, offline-first local workflow execution.

Eksporty modułu przez importy i konfigurację.

### `__main__.py`

Moduł implementacyjny silnika.

Eksporty modułu przez importy i konfigurację.

### `act_bridge.py`

Optional adapter to nektos/act (MIT); no GitHub-hosted runner invocation.

- `ActError {}`
- `ActBridge {__init__, command, run}`

### `actions.py`

Offline built-in actions. Unsupported third-party uses fail closed.

- `UnsupportedAction {}`
- `safe_subdir(workspace, subdir)`
- `execute_action(uses, params, workspace, run_id, artifacts, cache, source_repo, record_artifact, context, secrets)`

### `agent_gateway.py`

Scoped agent tools for local/ChatGPT API planning. No agent can approve or execute writes.

- `ToolError {}`
- `ToolGateway {__init__, invoke}`
- `openai_transport(payload, key)`
- `OpenAIOrchestrator {__init__, run}`

### `ai_bridge.py`

Deterministic offline intent router plus opt-in OpenAI or loopback Ollama planning.

- `AIUnavailable {}`
- `ChatPlanner {plan, model_plan}`

### `analysis.py`

Deterministic failure classification and explicit bounded retry policy.

- `FailureDiagnosis {}`
- `diagnose(log)`
- `retry_delay(attempt, base, cap)`

### `api.py`

Localhost-only FastAPI server. Mutation requires a random bearer-like CSRF token.

- `CompileRequest {}`
- `RunRequest {}`
- `ChatRequest {}`
- `OAuthStartRequest {}`
- `AgentRequest {}`
- `PlanRequest {}`
- `ModelDownloadRequest {}`
- `SimulationRequest {}`
- `SecretRequest {}`
- `create_app(settings)`

### `artifacts.py`

Path-safe artifact packaging, integrity manifest, and extraction.

- `ArtifactStore {__init__, _target, upload, verify, download}`

### `audit_ledger.py`

Transactional tamper-evident audit chain with owner-supplied HMAC key.

- `LedgerIntegrityError {}`
- `_canonical(data)`
- `IntegrityLedger {__init__, _db, _digest, append, events, verify}`
- `load_or_create_key(path)`

### `automation.py`

Explicit approval, allowlist and durable audit for GitHub mutations.

- `PolicyError {}`
- `ActionPlan {}`
- `ActionController {__init__, _connect, _validate, propose, approve, execute, history}`

### `billing.py`

User-configurable counterfactual billing estimates, not real GitHub invoices.

- `estimate(store, usd_per_minute, pln_per_usd)`

### `cache.py`

SHA-256 CAS and safe local cache restore; reflink fast path where available.

- `CAS {__init__, _path, put, get, put_file, restore_file}`
- `DependencyCache {__init__, _index, save, restore}`

### `cli.py`

Local CLI: execute, validate, serve, watch, simulate, vault and optional hooks.

- `main(argv)`

### `compatibility.py`

Read-only preflight capability inspection for local GitHub Actions workflows.

- `inspect_workflow(source)`

### `compiler.py`

Workflow compiler: validates jobs, expands matrices, resolves dependencies, detects cycles.

- `JobSpec {}`
- `CompiledWorkflow {}`
- `load_workflow(source)`
- `expand_matrix(matrix, limit)`
- `compile_workflow(source, max_matrix)`

### `config.py`

Runtime configuration, directories and trust boundaries.

- `Settings {from_env, prepare}`

### `digital_twin.py`

Discrete-event simulation of external dependencies, with explicit evidence boundaries.

- `simulate_architecture()`

### `dl_adapter.py`

Fail-closed Digital-Life local contract adapter and reversible migration journal.

- `MigrationError {}`
- `DigitalLifeAdapter {__init__, _validate, encode, decode}`
- `MigrationJournal {__init__, _db, _record, plan, _transition, start_shadow, approval_token, approve, activate, rollback}`

### `dl_contract.py`

Versioned owner-signed exchange contract for future Digital-Life integration.

- `ContractError {}`
- `_canonical(obj)`
- `negotiate_version(local, remote)`
- `ReplayGuard {__init__, _db, admit}`
- `SignedEnvelope {issue, verify}`

### `engine.py`

Async DAG orchestration, isolated workspaces, job/step state and offline actions.

- `Engine {__init__, cancel, run, _job, _execute_job, _execute_steps, _read_env_file}`

### `expressions.py`

Non-eval expression interpreter for a bounded subset of GitHub expression syntax.

- `ExpressionError {}`
- `Parser {__init__, peek, take, expect, parse, expr, lookup, call}`
- `truth(value)`
- `evaluate(expr, context)`
- `interpolate(value, context)`

### `github_oauth.py`

GitHub App device flow (RFC 8628). Authorization stays outside the model.

- `OAuthError {}`
- `github_oauth_transport(path, params)`
- `DeviceFlowManager {__init__, start, poll}`

### `hooks.py`

Explicit opt-in installation of local Git hooks; never invoked during package build.

- `install_hook(repo, event, workflow)`

### `inference.py`

Explicit opt-in llama.cpp subprocess adapter for installed local binaries.

- `InferenceError {}`
- `LlamaCli {__init__, build_command, run}`

### `model_cli.py`

GGUF/Hugging Face local CLI. No paid services or implicit GitHub Actions.

- `main(argv)`

### `model_studio.py`

Local GGUF inspection, validated generation parameters and resumable HF downloads.

- `GGUFError {}`
- `HFError {}`
- `ModelParameters {__post_init__, to_dict}`
- `GGUFInspector {inspect}`
- `hf_resolve_url(repo, revision, filename)`
- `_trusted_redirect(url)`
- `HFDownload {__init__, download}`
- `ModelCatalog {__init__, path, list, inspect}`

### `recovery.py`

Transactional at-least-once work queue with fenced leases and idempotent results.

- `DurableLeaseQueue {__init__, _db, submit, claim, heartbeat, complete, fail, recover, result}`

### `redaction.py`

Streaming Aho-Corasick secret masker with delayed output across chunk boundaries.

- `StreamMasker {__init__, _emit, feed, finish}`
- `redact(text, secrets)`

### `remote.py`

Bounded GitHub REST adapter. Never invokes GitHub-hosted Actions.

- `GitHubError {__init__}`
- `http_transport(method, url, headers, body)`
- `GitHubClient {__init__, _call, repo_path, repos, repo, workflows, create_branch, put_file, create_pr, status}`

### `resilience.py`

Bounded adaptive fault control with injectable monotonic time and deterministic jitter.

- `CircuitOpen {}`
- `AdaptiveCircuitBreaker {__init__, allow, record_success, record_failure, snapshot}`
- `RetryPolicy {__post_init__, delays}`
- `LatencyTelemetry {__init__, observe, snapshot}`

### `runner.py`

Native and Docker subprocess runner with timeouts, process-tree termination and redacted streams.

- `ExecutionDenied {}`
- `async terminate_tree(proc)`
- `async run_command(command, workspace, env, shell, timeout, secrets, on_log, engine, image, network, mount_root)`

### `schedule.py`

Local 5-field cron matching for optional polling daemon, no cloud scheduler.

- `field_matches(spec, value, minimum, maximum)`
- `matches(cron, now)`

### `scheduler.py`

Adaptive bounded local scheduler with EWMA CPU/RAM admission control.

- `AdaptiveScheduler {__init__, sample, acquire, release}`

### `services.py`

Docker service lifecycle for local-image-only job containers, isolated bridge network.

- `ServiceError {}`
- `async docker()`
- `DockerServices {__init__, __aenter__, __aexit__}`

### `simulator.py`

Deterministic synthetic GitHub event simulator and local workflow harness.

- `GitHubActionsDigitalTwin {__init__, dispatch, create_check, complete_check, upload_artifact}`
- `synthetic_event(name, seed)`
- `VirtualWorkerPool {__init__, execute}`
- `async simulate(workflow, repo, seed)`

### `storage.py`

SQLite WAL event store and execution history.

- `StateStore {__init__, execute, create_run, recover_interrupted, run_status, job_status, step_status, log, logs, add_artifact, get_artifact, run, list_runs, close, __del__}`

### `toolchains.py`

Read-only language toolchain discovery, no installations or implicit execution.

- `detect_toolchains(commands)`

### `vault.py`

Local encrypted secret vault. Argon2id -> AES-256-GCM plus HMAC-SHA3-256 envelope.

- `VaultError {}`
- `SecretVault {__init__, _derive, _read, _write, list, all, get, set, delete}`

### `yaml_loader.py`

Safe GitHub-compatible YAML 1.2-ish loader with bounded input and duplicate rejection.

- `WorkflowLoader {}`
- `unique_mapping(loader, node)`
- `load_yaml(source)`

## Moduły dodane v1.1

- `omega_actions.providers.ProviderGateway.chat`: obsługa openai-compatible, Anthropic, Gemini, Ollama; limit odpowiedzi 1 MiB, timeout, bez redirect.
- `omega_actions.providers.list_providers/get_provider`: zamknięty katalog 24 endpointów.
- `ProviderCatalog.java`: walidowany katalog JSON z zasobów APK.
- `NativeBridge.chatProvider`: asynchroniczne zapytania do zewnętrznych modeli; token z Keystore.
- `NativeBridge.runWorkflow`: lokalne wykonanie wskazanego YAML, jawne uprawnienie do wykonania.
- `RuntimeAssetsInstaller`: atomowe rozpakowanie zweryfikowanego ZIP backendu.
- `tools.verify_runtime_bundle.inspect_runtime_bundle`: bramka integralności ARM64.
- `tools.prepare_android_assets.package_backend`: deterministyczny ZIP źródeł Python.
