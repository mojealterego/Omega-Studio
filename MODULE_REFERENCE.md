# Module Reference — wygenerowany z rzeczywistego kodu

Poniższe sygnatury pochodzą bezpośrednio z parsera AST Python 3.13. 
Nazwy metod są zgodne z plikami paczki; opis wiersza to pierwszy wiersz docstringu, jeśli istnieje.

## Warstwa Python

### `backend/omega_actions/__init__.py`

OMEGA Actions Local Engine: explicit, offline-first local workflow execution.

- Moduł konfiguracji, danych lub rejestracji pakietu.

### `backend/omega_actions/__main__.py`

- Moduł konfiguracji, danych lub rejestracji pakietu.

### `backend/omega_actions/act_bridge.py`

Optional adapter to nektos/act (MIT); no GitHub-hosted runner invocation.

- **class `ActError`**
- **class `ActBridge`**
  - `ActBridge.command(self, repo, workflow, job)`
  - `ActBridge.run(self, repo, workflow, job, timeout)`

### `backend/omega_actions/actions.py`

Offline built-in actions. Unsupported third-party uses fail closed.

- **class `UnsupportedAction`**
- `safe_subdir(workspace, subdir)`
- `execute_action(uses, params, workspace, run_id, artifacts, cache, source_repo, record_artifact, context, secrets)`

### `backend/omega_actions/agent_gateway.py`

Scoped agent tools for local/ChatGPT API planning. No agent can approve or execute writes.

- **class `ToolError`**
- **class `ToolGateway`**
  - `ToolGateway.invoke(self, name, args)`
- `openai_transport(payload, key)`
- **class `OpenAIOrchestrator`**
  - `OpenAIOrchestrator.run(self, task, api_key, model, enabled, max_rounds)`

### `backend/omega_actions/ai_bridge.py`

Deterministic offline intent router plus opt-in OpenAI or loopback Ollama planning.

- **class `AIUnavailable`**
- **class `ChatPlanner`**
  - `ChatPlanner.plan(self, message)`
  - `ChatPlanner.model_plan(self, message, provider, model, api_key)`

### `backend/omega_actions/analysis.py`

Deterministic failure classification and explicit bounded retry policy.

- **class `FailureDiagnosis`**
- `diagnose(log)`
- `retry_delay(attempt, base, cap)`

### `backend/omega_actions/api.py`

Localhost-only FastAPI server. Mutation requires a random bearer-like CSRF token.

- **class `CompileRequest`**
- **class `RunRequest`**
- **class `ChatRequest`**
- **class `ProviderChatRequest`**
- **class `OAuthStartRequest`**
- **class `AgentRequest`**
- **class `PlanRequest`**
- **class `ModelDownloadRequest`**
- **class `SimulationRequest`**
- **class `SecretRequest`**
- `create_app(settings)`

### `backend/omega_actions/artifacts.py`

Path-safe artifact packaging, integrity manifest, and extraction.

- **class `ArtifactStore`**
  - `ArtifactStore._target(self, run_id, name)`
  - `ArtifactStore.upload(self, run_id, name, patterns, workspace, secrets)`
  - `ArtifactStore.verify(self, run_id, name)`
  - `ArtifactStore.download(self, run_id, name, destination)`

### `backend/omega_actions/audit_ledger.py`

Transactional tamper-evident audit chain with owner-supplied HMAC key.

- **class `LedgerIntegrityError`** — Stored audit records differ from the authenticated chain.
- `_canonical(data)`
- **class `IntegrityLedger`** — SQLite WAL, BEGIN IMMEDIATE serialization, HMAC-SHA256 chain; no external anchor.
  - `IntegrityLedger._db(self)`
  - `IntegrityLedger._digest(self, seq, event, payload, at_ns, previous)`
  - `IntegrityLedger.append(self, event, payload)`
  - `IntegrityLedger.events(self)`
  - `IntegrityLedger.verify(self)`
- `load_or_create_key(path)` — Create a private 256-bit key once, using exclusive creation and no symlink traversal.

### `backend/omega_actions/automation.py`

Explicit approval, allowlist and durable audit for GitHub mutations.

- **class `PolicyError`**
- **class `ActionPlan`**
- **class `ActionController`**
  - `ActionController._connect(self)`
  - `ActionController._validate(self, operation, repo, args)`
  - `ActionController.propose(self, operation, repo, args)`
  - `ActionController.approve(self, pid)`
  - `ActionController.execute(self, pid)`
  - `ActionController.history(self, limit)`

### `backend/omega_actions/billing.py`

User-configurable counterfactual billing estimates, not real GitHub invoices.

- `estimate(store, usd_per_minute, pln_per_usd)`

### `backend/omega_actions/cache.py`

SHA-256 CAS and safe local cache restore; reflink fast path where available.

- **class `CAS`**
  - `CAS._path(self, digest)`
  - `CAS.put(self, data)`
  - `CAS.get(self, digest)`
  - `CAS.put_file(self, source)`
  - `CAS.restore_file(self, digest, destination)`
- **class `DependencyCache`**
  - `DependencyCache._index(self, key)`
  - `DependencyCache.save(self, key, paths, workspace, secrets)`
  - `DependencyCache.restore(self, key, workspace, restore_keys)`

### `backend/omega_actions/cli.py`

Local CLI: execute, validate, serve, watch, simulate, vault and optional hooks.

- `main(argv)`

### `backend/omega_actions/compatibility.py`

Read-only preflight capability inspection for local GitHub Actions workflows.

- `inspect_workflow(source)`

### `backend/omega_actions/compiler.py`

Workflow compiler: validates jobs, expands matrices, resolves dependencies, detects cycles.

- **class `JobSpec`**
- **class `CompiledWorkflow`**
- `load_workflow(source)`
- `expand_matrix(matrix, limit)`
- `compile_workflow(source, max_matrix)`

### `backend/omega_actions/config.py`

Runtime configuration, directories and trust boundaries.

- **class `Settings`**
  - `Settings.from_env(cls)`
  - `Settings.prepare(self)`

### `backend/omega_actions/digital_twin.py`

Discrete-event simulation of external dependencies, with explicit evidence boundaries.

- `simulate_architecture(seed, jobs, worker_count, network_failure_rate)` — Simulate GitHub API/HF transfer/AI calls and Android process restarts.

### `backend/omega_actions/dl_adapter.py`

Fail-closed Digital-Life local contract adapter and reversible migration journal.

- **class `MigrationError`** — Invalid migration state or owner authorization.
- **class `DigitalLifeAdapter`** — Encode and decode authenticated local messages; performs no external I/O.
  - `DigitalLifeAdapter._validate(cls, capability, data)`
  - `DigitalLifeAdapter.encode(self, capability, data, now, nonce)`
  - `DigitalLifeAdapter.decode(self, envelope, now)`
- **class `MigrationJournal`** — SQLite two-phase admission; activation changes only local migration metadata.
  - `MigrationJournal._db(self)`
  - `MigrationJournal._record(self, profile)`
  - `MigrationJournal.plan(self, profile, source, target, digest)`
  - `MigrationJournal._transition(self, profile, expected, target)`
  - `MigrationJournal.start_shadow(self, profile)`
  - `MigrationJournal.approval_token(self, profile)`
  - `MigrationJournal.approve(self, profile, token)`
  - `MigrationJournal.activate(self, profile)`
  - `MigrationJournal.rollback(self, profile)`

### `backend/omega_actions/dl_contract.py`

Versioned owner-signed exchange contract for future Digital-Life integration.

- **class `ContractError`** — Invalid, expired, replayed or unauthorized envelope.
- `_canonical(obj)`
- `negotiate_version(local, remote)`
- **class `ReplayGuard`** — SQLite nonce store, transactional uniqueness per tenant and protocol.
  - `ReplayGuard._db(self)`
  - `ReplayGuard.admit(self, tenant, nonce, now, expires_at)`
- **class `SignedEnvelope`**
  - `SignedEnvelope.issue(cls, tenant, kind, payload, key, now, ttl, nonce)`
  - `SignedEnvelope.verify(cls, envelope, key, now, tenant, replay_guard)`

### `backend/omega_actions/engine.py`

Async DAG orchestration, isolated workspaces, job/step state and offline actions.

- **class `Engine`**
  - `Engine.cancel(self, run_id)`
  - `async Engine.run(self, workflow, repo, secrets, event, event_payload, run_id, engine)`
  - `async Engine._job(self, run_id, job, repo, workflow, secrets, gitctx, deps, mode)`
  - `async Engine._execute_job(self, run_id, job, repo, workflow, secrets, ctx, mode)`
  - `async Engine._execute_steps(self, run_id, job, repo, workflow, secrets, ctx, mode, workspace, io_dir, envfile, outputfile, summaryfile, base_env, steps, pending_cache, started, job_timeout, selected, services_context)`
  - `Engine._read_env_file(path)`

### `backend/omega_actions/expressions.py`

Non-eval expression interpreter for a bounded subset of GitHub expression syntax.

- **class `ExpressionError`**
- **class `Parser`**
  - `Parser.peek(self)`
  - `Parser.take(self)`
  - `Parser.expect(self, token)`
  - `Parser.parse(self)`
  - `Parser.expr(self, min_bp)`
  - `Parser.lookup(self, key)`
  - `Parser.call(self, name, args)`
- `truth(value)`
- `evaluate(expr, context)`
- `interpolate(value, context)`

### `backend/omega_actions/github_oauth.py`

GitHub App device flow (RFC 8628). Authorization stays outside the model.

- **class `OAuthError`**
- `github_oauth_transport(path, params)`
- **class `DeviceFlowManager`**
  - `DeviceFlowManager.start(self, client_id)`
  - `DeviceFlowManager.poll(self)`

### `backend/omega_actions/hooks.py`

Explicit opt-in installation of local Git hooks; never invoked during package build.

- `install_hook(repo, event, workflow)`

### `backend/omega_actions/inference.py`

Explicit opt-in llama.cpp subprocess adapter for installed local binaries.

- **class `InferenceError`**
- **class `LlamaCli`**
  - `LlamaCli.build_command(self, model, settings, prompt)`
  - `LlamaCli.run(self, model, settings, prompt, timeout)`

### `backend/omega_actions/model_cli.py`

GGUF/Hugging Face local CLI. No paid services or implicit GitHub Actions.

- `main(argv)`

### `backend/omega_actions/model_studio.py`

Local GGUF inspection, validated generation parameters and resumable HF downloads.

- **class `GGUFError`** — Malformed or unsupported GGUF metadata.
- **class `HFError`** — Download failed without exposing an authentication token.
- **class `ModelParameters`**
  - `ModelParameters.to_dict(self)`
- **class `GGUFInspector`**
  - `GGUFInspector.inspect(cls, path)`
- `hf_resolve_url(repo, revision, filename)`
- `_trusted_redirect(url)`
- **class `HFDownload`**
  - `HFDownload.download(self, repo, revision, filename, target, token, expected_sha256)`
- **class `ModelCatalog`**
  - `ModelCatalog.path(self, name)`
  - `ModelCatalog.list(self)`
  - `ModelCatalog.inspect(self, name)`

### `backend/omega_actions/providers.py`

Fail-closed, opt-in multi-provider chat gateway.

- **class `ProviderError`** — Safe, redacted error suitable for the UI.
- **class `Provider`**
- `get_provider(provider_id)`
- `list_providers()`
- **class `ProviderGateway`**
  - `async ProviderGateway.chat(self, provider_id, model, message, api_key, enable_remote, max_tokens)`

### `backend/omega_actions/recovery.py`

Transactional at-least-once work queue with fenced leases and idempotent results.

- **class `DurableLeaseQueue`** — Leases fence stale workers; consumers must make external effects idempotent.
  - `DurableLeaseQueue._db(self)`
  - `DurableLeaseQueue.submit(self, job_id, payload, now)`
  - `DurableLeaseQueue.claim(self, worker, now, lease_seconds)`
  - `DurableLeaseQueue.heartbeat(self, job_id, worker, now, lease_seconds)`
  - `DurableLeaseQueue.complete(self, job_id, worker, result, now)`
  - `DurableLeaseQueue.fail(self, job_id, worker, now)`
  - `DurableLeaseQueue.recover(self, now)`
  - `DurableLeaseQueue.result(self, job_id)`

### `backend/omega_actions/redaction.py`

Streaming Aho-Corasick secret masker with delayed output across chunk boundaries.

- **class `StreamMasker`**
  - `StreamMasker._emit(self, final)`
  - `StreamMasker.feed(self, text)`
  - `StreamMasker.finish(self)`
- `redact(text, secrets)`

### `backend/omega_actions/remote.py`

Bounded GitHub REST adapter. Never invokes GitHub-hosted Actions.

- **class `GitHubError`**
- `http_transport(method, url, headers, body)`
- **class `GitHubClient`**
  - `GitHubClient._call(self, method, path, data)`
  - `GitHubClient.repo_path(repo)`
  - `GitHubClient.repos(self)`
  - `GitHubClient.repo(self, repo)`
  - `GitHubClient.workflows(self, repo)`
  - `GitHubClient.create_branch(self, repo, branch, sha)`
  - `GitHubClient.put_file(self, repo, branch, path, content, message, sha)`
  - `GitHubClient.create_pr(self, repo, title, head, base, body)`
  - `GitHubClient.status(self, repo, sha, state, description)`

### `backend/omega_actions/resilience.py`

Bounded adaptive fault control with injectable monotonic time and deterministic jitter.

- **class `CircuitOpen`** — The target has exceeded its failure budget or half-open probe limit.
- **class `AdaptiveCircuitBreaker`** — Thread-safe CLOSED/OPEN/HALF_OPEN breaker; a single half-open probe at a time.
  - `AdaptiveCircuitBreaker.allow(self)`
  - `AdaptiveCircuitBreaker.record_success(self)`
  - `AdaptiveCircuitBreaker.record_failure(self)`
  - `AdaptiveCircuitBreaker.snapshot(self)`
- **class `RetryPolicy`** — At most max_attempts total attempts, with deterministic seedable full-ish jitter.
  - `RetryPolicy.delays(self, seed)`
- **class `LatencyTelemetry`** — Bounded sliding window; percentiles describe observed samples, not hard RT guarantees.
  - `LatencyTelemetry.observe(self, metric, elapsed_ms)`
  - `LatencyTelemetry.snapshot(self, metric)`

### `backend/omega_actions/runner.py`

Native and Docker subprocess runner with timeouts, process-tree termination and redacted streams.

- **class `ExecutionDenied`**
- `async terminate_tree(proc)`
- `async run_command(command, workspace, env, shell, timeout, secrets, on_log, engine, image, network, mount_root)`

### `backend/omega_actions/schedule.py`

Local 5-field cron matching for optional polling daemon, no cloud scheduler.

- `field_matches(spec, value, minimum, maximum)`
- `matches(cron, now)`

### `backend/omega_actions/scheduler.py`

Adaptive bounded local scheduler with EWMA CPU/RAM admission control.

- **class `AdaptiveScheduler`**
  - `AdaptiveScheduler.sample(self)`
  - `async AdaptiveScheduler.acquire(self)`
  - `async AdaptiveScheduler.release(self)`

### `backend/omega_actions/services.py`

Docker service lifecycle for local-image-only job containers, isolated bridge network.

- **class `ServiceError`**
- `async docker(*args, timeout)`
- **class `DockerServices`**

### `backend/omega_actions/simulator.py`

Deterministic synthetic GitHub event simulator and local workflow harness.

- **class `GitHubActionsDigitalTwin`** — In-memory GitHub Checks/Actions event contract, without network access.
  - `GitHubActionsDigitalTwin.dispatch(self, event)`
  - `GitHubActionsDigitalTwin.create_check(self, sha, name)`
  - `GitHubActionsDigitalTwin.complete_check(self, key, conclusion)`
  - `GitHubActionsDigitalTwin.upload_artifact(self, name, content)`
- `synthetic_event(name, seed)`
- **class `VirtualWorkerPool`** — Seeded virtual worker scheduling for external architecture contract tests.
  - `VirtualWorkerPool.execute(self, workflow, fail_jobs)`
- `async simulate(workflow, repo, seed)`

### `backend/omega_actions/storage.py`

SQLite WAL event store and execution history.

- **class `StateStore`**
  - `StateStore.execute(self, sql, args)`
  - `StateStore.create_run(self, run_id, workflow, repo, event, payload)`
  - `StateStore.recover_interrupted(self)` — Mark interrupted runs as failed; call only when no other owner is executing.
  - `StateStore.run_status(self, run_id, status)`
  - `StateStore.job_status(self, run_id, jid, status)`
  - `StateStore.step_status(self, run_id, jid, idx, name, status, duration)`
  - `StateStore.log(self, run_id, jid, idx, text)`
  - `StateStore.logs(self, run_id, since, limit)`
  - `StateStore.add_artifact(self, run_id, name, path, count, digest)`
  - `StateStore.get_artifact(self, run_id, name)`
  - `StateStore.run(self, run_id)`
  - `StateStore.list_runs(self, limit)`
  - `StateStore.close(self)`

### `backend/omega_actions/toolchains.py`

Read-only language toolchain discovery, no installations or implicit execution.

- `detect_toolchains(commands)`

### `backend/omega_actions/ultimate/__init__.py`

OMEGA Studio Ultimate: bounded local engineering components.

- Moduł konfiguracji, danych lub rejestracji pakietu.

### `backend/omega_actions/ultimate/__main__.py`

OMEGA Studio Ultimate standalone CLI for local, explicit operations.

- `main(argv)`

### `backend/omega_actions/ultimate/archives.py`

Deterministic ZIP and optional native RAR with strict extraction boundaries.

- **class `ArchiveError`**
- `_relative_member(name)`
- `pack_zip(source, destination, max_files)`
- `extract_zip(source, destination, max_files, max_total_bytes, max_ratio)`
- `pack_rar(source, destination, timeout)` — Use installed licensed RAR encoder; fail closed when absent.
- `extract_rar(source, destination, max_files, max_total_bytes)` — Bounded RAR extraction using rarfile; compressed RAR requires compatible decoder.

### `backend/omega_actions/ultimate/assets.py`

Offline procedural SVG/PNG/WAV/glTF assets; no model inference is claimed.

- `make_svg(text, size)`
- `make_png(width, height, rgb)`
- `make_wav(frequency, duration, sample_rate)`
- `make_gltf_animation(duration)` — Valid glTF 2.0 cube animated in 3D over time (3D + time).
- `make_video(destination, duration, fps, width, height)` — Generate original procedural MP4 via a locally installed FFmpeg encoder.

### `backend/omega_actions/ultimate/cloud.py`

Read-only cloud catalog endpoints. Fixed hosts prevent user-supplied SSRF targets.

- **class `CloudError`**
- **class `MultiCloudHub`**
  - `MultiCloudHub.close(self)`
  - `MultiCloudHub._get(self, url, params, token)`
  - `MultiCloudHub.gitlab_projects(self, page, per_page, token)`
  - `MultiCloudHub.hf_models(self, limit, token)`
  - `MultiCloudHub.drive_files(self, token, page_token, page_size)`

### `backend/omega_actions/ultimate/code_swarm.py`

Bounded parallel static code analysis for Chat Leak/Duo offline engineering mode.

- `_finding(rule, severity, line, message)`
- `_unsafe_calls(tree)`
- `_secrets(tree)`
- `_complexity(tree)`
- `_imports(tree)`
- `analyze_source(source, mode)`

### `backend/omega_actions/ultimate/crawler.py`

GitHub organization catalog and explicitly requested local source snapshots.

- **class `CrawlerError`**
- `_name(value)`
- **class `GitHubOrgCrawler`**
  - `GitHubOrgCrawler.close(self)`
  - `GitHubOrgCrawler.crawl(self, organization, pages, per_page)`
  - `GitHubOrgCrawler.download_snapshot(self, organization, repository, revision, destination, max_archive_bytes)`
- **class `RepositoryIndex`**
  - `RepositoryIndex.upsert(self, items)`
  - `RepositoryIndex.search(self, term, limit)`
  - `RepositoryIndex.count(self)`

### `backend/omega_actions/ultimate/remote8080.py`

Opt-in authenticated remote workspace server with TLS required outside loopback.

- **class `RemoteError`**
- **class `RemoteConfig`**
- **class `WriteRequest`**
- `create_remote_app(workspace, username, password)`
- `serve(workspace, config)`

### `backend/omega_actions/ultimate/router.py`

Local-only authenticated OMEGA Ultimate API routes for existing FastAPI backend.

- **class `AssetRequest`**
- **class `SwarmRequest`**
- **class `NoCodeRequest`**
- `create_ultimate_router(home)`

### `backend/omega_actions/ultimate/seal.py`

Reproducible AST topology metrics and authenticated source integrity seal.

- `graph_invariants(vertices, edges)`
- `_ast_graph(root)`
- `seal_python_source(source, secret)`
- `verify_seal(source, seal, secret)`

### `backend/omega_actions/ultimate/simulation.py`

Deterministic simulation harness for external services; not device verification.

- `run_simulation(seed, jobs)`

### `backend/omega_actions/ultimate/streamer.py`

Bounded mmap reader and kernel-assisted file copier for large local assets.

- **class `WindowedReader`** — Random access to arbitrarily large addressable files with bounded mapping size.
  - `WindowedReader.read_at(self, offset, length)`
  - `WindowedReader.iter_chunks(self)`
  - `WindowedReader.digest(self)`
- `copy_file(source, destination, chunk_size)` — Atomic bounded-memory copy; use sendfile when supported, verify SHA-256.

### `backend/omega_actions/ultimate/swarm.py`

Bounded agent coordination with graph diffusion heuristic and explicit verification.

- **class `SwarmError`**
- **class `LoadBalancer`** — Conservative graph diffusion: sum of loads is invariant at each step.
  - `LoadBalancer.diffuse(self, loads, rate, steps)`
- **class `SwarmCoordinator`** — Bounded in-flight work; no autonomous network calls or repository mutation.
  - `SwarmCoordinator._run(self, fn, item)`
  - `SwarmCoordinator.map(self, fn, items)`
- **class `DuoCoordinator`** — Generator/verifier cycle with hard attempt budget and no silent acceptance.
  - `DuoCoordinator.run(self, generator, verifier, request)`

### `backend/omega_actions/vault.py`

Local encrypted secret vault. Argon2id -> AES-256-GCM plus HMAC-SHA3-256 envelope.

- **class `VaultError`**
- **class `SecretVault`**
  - `SecretVault._derive(self, salt)`
  - `SecretVault._read(self)`
  - `SecretVault._write(self, values)`
  - `SecretVault.list(self)`
  - `SecretVault.all(self)`
  - `SecretVault.get(self, key)`
  - `SecretVault.set(self, key, value)`
  - `SecretVault.delete(self, key)`

### `backend/omega_actions/yaml_loader.py`

Safe GitHub-compatible YAML 1.2-ish loader with bounded input and duplicate rejection.

- **class `WorkflowLoader`**
- `unique_mapping(loader, node)`
- `load_yaml(source)`

## Android Java

Android sources reside in `android/app/src/main/java/org/omega/actions`. The following class names are extracted from source files; compilation against Android SDK is a separate gate.

- `android/app/src/main/java/org/omega/actions/CodeEditorActivity.java` — CodeEditorActivity
- `android/app/src/main/java/org/omega/actions/CodeServerManager.java` — CodeServerManager, Session
- `android/app/src/main/java/org/omega/actions/MainActivity.java` — MainActivity
- `android/app/src/main/java/org/omega/actions/NativeBridge.java` — NativeBridge
- `android/app/src/main/java/org/omega/actions/ProviderCatalog.java` — ProviderCatalog
- `android/app/src/main/java/org/omega/actions/RuntimeAssetsInstaller.java` — RuntimeAssetsInstaller
- `android/app/src/main/java/org/omega/actions/RuntimeEnvironment.java` — RuntimeEnvironment
- `android/app/src/main/java/org/omega/actions/RuntimeHealth.java` — RuntimeHealth
- `android/app/src/main/java/org/omega/actions/SecureVault.java` — SecureVault
- `android/app/src/main/java/org/omega/actions/TermuxBootstrapInstaller.java` — TermuxBootstrapInstaller
- `android/app/src/main/java/org/omega/actions/core/GgufMetadataReader.java` — GgufMetadataReader
- `android/app/src/main/java/org/omega/actions/core/HfUrl.java` — HfUrl

## Statystyki referencji

- Pliki Python: **54**.
- Klasy Python: **87**.
- Funkcje/metody Python: **211**.
- Pliki Java: **12**.

## Kontrakty

Publiczne HTTP/JSON: `API_REFERENCE.md`. Bezpieczeństwo i zaufanie: `SECURITY_ARCHITECTURE.md`. Wymagania binarne Android: `BUILD_AND_DEPLOYMENT_GUIDE.md`.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
