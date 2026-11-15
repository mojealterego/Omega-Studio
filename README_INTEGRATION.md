# OMEGA-ZTF-003 × ORG-001 — przyrost weryfikacyjny do Omega-Studio/main

To **przyrost źródłowy**, nie pełny model AI, nie ważący setki GB checkpoint i nie gotowy APK.

## Integracja bez nadpisywania istniejących komponentów

Zawartość katalogów w archiwum jest przeznaczona do skopiowania do katalogu głównego repozytorium `mojealterego/Omega-Studio` na `main`, z zachowaniem dotychczasowych plików. Nie kopiować testowej lokalnej atrapy `safetensors_guard.py` — **nie została dołączona do archiwum**. Istniejący moduł w repozytorium pozostaje autorytatywny.

Dodane pliki:

- `backend/omega_actions/ultimate/ztf_admission.py`
- `backend/omega_actions/ultimate/c2_blending.py`
- `backend/tests/test_ztf_admission.py`
- `backend/tests/test_c2_blending.py`
- `backend/tests/test_verify_ztf_intake_cli.py`
- `tools/verify_ztf_intake.py`
- `docs/OMEGA_ZTF_003_ORG_001_INTAKE_AUDIT_2026-11-15.md`
- `verification/OMEGA_ZTF_003_ORG_001_PATCH_EVIDENCE_2026-11-15.json`

## Testy po integracji do repo

```bash
PYTHONPATH=backend:. python3 -m pytest -q backend/tests/test_ztf_admission.py backend/tests/test_c2_blending.py backend/tests/test_verify_ztf_intake_cli.py
python3 -m compileall -q backend/omega_actions/ultimate/ztf_admission.py backend/omega_actions/ultimate/c2_blending.py tools/verify_ztf_intake.py
```

CLI:

```bash
python3 tools/verify_ztf_intake.py --manifest models/UNIFIED_MODEL_MANIFEST.json --artifacts-root /trusted/model-files --artifact-map artifact_map.json
```

Kod nie ma funkcji trenowania, generowania, nadawania uprawnień ani promocji modelu do wydania. Wynik `INTEGRITY_VERIFIED_ONLY` nigdy nie jest podstawą do statusu `RELEASED`. Szczegóły w dokumentacji przyrostu.
