# Skills Hub — evidence reconciliation (2026-11-10)

## Verified on main

At commit `bc8abe780fa02e4ad5718512ed04bee18b3e3cf4`, the recursive Git tree includes:
- `config/skills_sources.lock.json`
- `backend/omega_actions/ultimate/skills_sources.lock.json`
- `docs/SKILLS_INTEGRATION.md`

The tree does **not** contain `backend/omega_actions/ultimate/skills_hub.py`, `skills_cli.py`, or a checked-in collection of upstream `SKILL.md` files.

## Correct interpretation

The 11 upstream repositories are **registered as source metadata**, not demonstrated as fully installed, executed or integrated. The recorded counts in the lock file are declarations and must be verified against pinned Git trees. A curated index and a CLI repository must not be counted as installed skills.

Previous statements of 236 Python tests, 19 JavaScript tests and browser verification in `docs/SKILLS_INTEGRATION.md` are historical claims, **not verification performed in this audit**. Do not use them as a release gate.

## Required acceptance evidence

1. Inventory every pinned upstream `SKILL.md` with path, SHA-256, license and source commit.
2. Review individual licenses and reject unapproved executable content.
3. Implement bounded ZIP extraction with ZipSlip, symlink, duplicate and decompression limits; verify against adversarial tests.
4. Implement deterministic search and explicit opt-in context composition; treat imported instructions as untrusted data.
5. Demonstrate Android integration and actual offline tests with archived test logs.
6. Demonstrate ARM64 runtime binaries, APK signing and real device E2E independently from Skills Hub.

No automatic upstream code execution, paid GitHub Actions, or modification of Digital-Life is authorized.
