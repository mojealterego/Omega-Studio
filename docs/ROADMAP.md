# OMEGA Studio — release gates and implementation ledger

Baseline inspected: `main`, commit `fe74b37a097193838de5b2928e397809105650a4` (2026-11-12). This ledger is not proof of build or deployment.

## Release blocking requirements

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| AND-01 | Self-contained Android ARM64 APK with Termux-compatible userspace | Extracted signed APK, ELF inventory, loader smoke tests on physical Android | BLOCKED / not demonstrated |
| AND-02 | Python executable and standard library | Device execution of `python3 -c 'import ssl,sqlite3; print("ok")'` | BLOCKED |
| AND-03 | Git executable and HTTPS transport | Device `git --version` and TLS clone against disposable test repository | BLOCKED |
| AND-04 | llama.cpp inference | Device GGUF inference with measured memory, thermal throttling and crash recovery | BLOCKED |
| AND-05 | VS Code-compatible editing environment | Device edit/save/reopen and process lifecycle test | BLOCKED |
| AND-06 | Signed APK release | `apksigner verify`, bootstrap gate and clean-install device E2E | BLOCKED |
| APP-01 | Web/Android Code-NoCode builder | Reversible serialization, project export, actual web build and signed Android build | NOT VERIFIED |
| CI-01 | Independent workflow runner | Offline workflow execution, retry, cancellation, log persistence, restart recovery | NOT VERIFIED |
| GAME-STATE-01 | Persistent FactoryRunner checkpoints | Storage CAS, process restart, fail-closed recovery, adversarial tests | SOURCE IMPLEMENTED; 9 LOCAL HOST TESTS PASS; no Android/device or full production-worker proof |
| SEC-01 | Tenant/workspace isolation | Symlink race, path traversal, cross-tenant and file-descriptor pinning regression tests | PARTIAL: source commits exist; test execution not independently verified |
| API-01 | Provider API keys | Encrypted at rest, redaction, rotation and authorization tests | NOT VERIFIED |

## Evidence policy

- `IMPLEMENTED` requires source at pinned commit.
- `HOST_TESTED` requires reproducible logs with command, runtime, exit code and commit SHA.
- `DEVICE_TESTED` requires physical Android device details, artifact digest and command outputs.
- `RELEASED` requires a signed artifact with SHA-256 and verified installation.
- A preview APK or a source checkout must never be labeled a complete native distribution.

## Next implementation order

1. Build deterministic ARM64 binary manifest and dependency closure for Python, Git, llama.cpp and code-server/VS Code-compatible editor.
2. Implement secure first-run bootstrap: no world-writable executables, bounded extraction, checksum and signature validation, rollback on failure.
3. Assemble the signed APK and run the existing `tools/verify_android_apk_release.py` gate.
4. Run instrumentation and E2E on an actual Android device; publish machine-readable evidence.
5. Validate AppBuilder outputs and standalone workflow runner; then promote release only when every blocking gate passes.
6. Integrate `FileFactoryStore` into an actual Game Factory host runtime, validate the real build worker and artifact hashes, and verify host recovery. Source and focused host evidence: `docs/GAME_FACTORY_PERSISTENCE.md`; storage tests alone do not close the production release gate.

## Constraints

Work on `main`; do not create additional branches. Do not use paid GitHub Actions as a prerequisite. Never replace physical-device evidence with a simulation. This document records outstanding work, not completion.
