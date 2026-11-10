# Dependencies & Licenses

## Zależności runtime Python

| Pakiet | Zakres / status | Licencja orientacyjna |
|---|---|---|
| Python | ≥3.11 | PSF |
| FastAPI | ≥0.110,<1 | MIT |
| Uvicorn | ≥0.27,<1 | BSD-3-Clause |
| PyYAML | ≥6,<7 | MIT |
| cryptography | ≥42,<50 | Apache-2.0 / BSD |
| argon2-cffi | ≥23,<26 | MIT |
| psutil | ≥5.9,<8 | BSD-3-Clause |
| httpx | ≥0.27,<1 | BSD-3-Clause |
| rarfile | opcjonalne ≥4.2,<5 | ISC (sprawdzić przy redystrybucji) |

`backend/requirements.txt` jest podstawowym manifestem. W zależności od instalacji występują zależności pośrednie Pydantic, Starlette, anyio, httpcore, certifi, h11, cffi, argon2-cffi-bindings, PyNaCl lub inne; dokładne wersje należy odczytać z lockfile środowiska build. Paczka nie vendoryzuje binariów tych bibliotek.

## Narzędzia opcjonalne

- Node.js — testy JS, potencjalny code-server; licencja Node.js/MIT + komponenty zależne.
- FFmpeg — generacja MP4; LGPL/GPL zależnie od konfiguracji build; binarium **nie jest dystrybuowane** w ZIP.
- `rar` — licencjonowany koder RAR, nie dołączony.
- `unrar`/`unar` — zewnętrzny dekoder RAR; licencja zależna od programu, nie dołączony.
- Android SDK/AGP/Gradle/NDK — wymagane do budowania natywnego APK, nie dołączone.
- Termux/termux-packages — źródła upstream, pakiety mają odrębne licencje, nie dołączono gotowych binariów.
- code-server (MIT) / Code-OSS (MIT, odróżnić od dystrybucji Microsoft Visual Studio Code) — menedżer jest w kodzie, binaria nie są dołączone.
- llama.cpp (MIT) — adapter/manifest i kontrola binariów; brak binarium ARM64.

## Materiały własne i źródła

`references/MCode.pdf` oraz tekst promptu zostały dostarczone przez użytkownika. Źródła OMEGA Studio pochodzą z własnego repozytorium użytkownika i lokalnych plików wcześniejszego projektu. Kod bazowy zawiera licencję Apache-2.0 w `LICENSE` i `backend/LICENSE`.

Indeksowane repozytoria z GitHub/GitLab/HF **nie są automatycznie dołączane** do ZIP. Metadane licencji SPDX są informacyjne; przed kopiowaniem kodu obowiązuje licencja danego repozytorium.

## Oficjalne źródła API

- GitHub: https://docs.github.com/en/rest/repos/repos#list-organization-repositories
- GitHub pagination: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
- GitLab: https://docs.gitlab.com/api/projects/
- Hugging Face: https://huggingface.co/docs/hub/api
- Hugging Face download: https://huggingface.co/docs/huggingface_hub/en/guides/download
- Termux: https://github.com/termux/termux-app
- code-server: https://github.com/coder/code-server
- llama.cpp: https://github.com/ggml-org/llama.cpp
- glTF 2.0: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html

Brak pełnego SBOM dla niepobranego natywnego runtime ARM64; żadne licencje nie są automatycznie uznawane za zgodne tylko dlatego, że projekt jest publiczny.

## Zewnętrzne źródła OSS — przypięte commity

Źródła, licencje, identyfikatory commitów, proces pobierania i zasady bezpiecznej redystrybucji opisuje [OSS_UPSTREAM_INTEGRATION.md](docs/OSS_UPSTREAM_INTEGRATION.md). Źródłem prawdy dla wersji jest `config/upstreams.lock.json`.
