# OMEGA Studio — durable Game Factory checkpoints

## Implemented scope

Source: `src/gamebuilder/FileFactoryStore.mjs`.
Tests: `tests/gamebuilder/FileFactoryStore.test.mjs`.

`FileFactoryStore` implements the existing `StateStore` contract from `src/gamebuilder/FactoryPipeline.ts`. It is intended for a trusted local Node.js host with a private state directory and atomic rename semantics.

- One JSON envelope per project, with SHA-256 over the serialized state.
- File descriptor reads with `O_NOFOLLOW` and regular-file checks.
- Per-project exclusive short-lived write lock with bounded retries.
- Expected-revision compare-and-swap on every write; atomic temporary-file publication with file and directory fsync.
- Strict project identifiers, revisions, statuses, receipt schema, and state-size limits.
- Explicit `recoverInterrupted` operation to mark a persisted `running` stage as `paused` only after an operator confirms that no old worker is still active.

## How to use

Pass the store to `FactoryRunner` instead of `InMemoryFactoryStore`:

```js
import { FileFactoryStore } from './src/gamebuilder/FileFactoryStore.mjs';
// FactoryRunner is defined in src/gamebuilder/FactoryPipeline.ts.
// It is imported through the TypeScript loader/bundler used by the host.
const stateStore = new FileFactoryStore('/private/omega-factory-state');
const runner = new FactoryRunner(stateStore, registeredWorkers);
```

`registeredWorkers` must provide actual execution adapters for the 16 stages. Neither this storage module nor the in-memory test workers generate a game or build an APK.

Run the standalone regression suite without installing dependencies:

```sh
node --test tests/gamebuilder/FileFactoryStore.test.mjs
```

Local focused run on Node 22.16.0 (13 November 2026): **7 PASS / 0 FAIL**. GitHub Actions were deliberately not executed.

## Operational and security boundaries

- SHA-256 detects accidental or unsophisticated corruption; it is not an authenticated MAC and does not protect against a privileged user rewriting both data and digest.
- Locks are not automatically reclaimed after a crash. If a stale `.lock` remains, stop all workers, inspect process ownership, reconcile the previous stage's external effects, then remove that single orphan lock before resuming.
- `recoverInterrupted(..., {operatorConfirmedNoActiveWorker: true})` is an explicit operator assertion, not independent process-liveness verification. If an old worker is still active, recovery must not be invoked.
- Atomic filesystem semantics require a local filesystem with reliable `rename`/`fsync`; distributed network filesystems, hostile same-user writers, and cross-host multi-tenant production execution are **not validated**.
- A checkpoint receipt is not evidence of a successful Unity/Unreal/Godot build. Artifact existence and SHA-256 verification remain the responsibility of a real build verifier.
- This change does not modify Android native runtime availability, APK signing, physical-device testing, or the release gate.
