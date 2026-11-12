# OMEGA STUDIO — WorkspaceRegistry P0 isolation hardening

Date: 2026-11-12. Target: `main`, `backend/omega_actions/ultimate/workspace_registry.py`.

## Reproduced defect

The previous implementation followed a `workspaces` root symlink. An adversarial or corrupted local home could redirect `create`, `open`, and `list` into an arbitrary directory reachable by the backend process. New regression tests reproduced the issue before the fix (4 failures and 1 missing-API error out of 8 tests).

## Implemented

- Secure, file-descriptor-based `openat`/`mkdirat` patterns through Python's `dir_fd`; directory descriptors use `O_DIRECTORY`, `O_NOFOLLOW`, and `O_CLOEXEC` where available.
- Reject root and child symlinks without following them. Verify directory type and effective process owner using `fstat`.
- Root directory locked to mode `0700`, including migration from existing standard-permission directories. Newly created children use mode `0700`.
- Directory enumeration uses an open root fd and `os.stat(..., follow_symlinks=False)` to prevent symlink traversal.
- `open_fd(name)` context manager exposes an anchored fd for callers that need race-resistant downstream operations. Its descriptor is closed on context exit.
- Existing `create`, `open`, `list` Path-returning API maintained for compatibility.

## Verified locally

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_workspace_registry*.py' -v
```

15 focused tests passed: four legacy tests and eleven new tests. Python module also passed `compileall`. Verification took place on a Linux host, **not** in Android's runtime, and does **not** prove a complete native APK.

## Residual security boundaries

Returning `Path` from `create` or `open` is retained for API compatibility. That path can be replaced after validation; it must **not** be treated as a durable security handle. Security-sensitive downstream file access should be performed relative to the held descriptor from `open_fd`, with `dir_fd` and `O_NOFOLLOW` for every subsequent operation. This change does not audit every downstream file operation, nor does it establish multi-tenant OS isolation, mount namespaces, or containerization.

## Release gate

`Android SDK/NDK`, full ARM64 binary payload, hardware tests (Samsung S24 Ultra / Android 17), device-side GGUF inference and signed APK remain unverified. The archive produced for this change is a source/test overlay, not an APK or the complete repository.
