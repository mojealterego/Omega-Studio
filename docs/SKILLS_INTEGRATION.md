# OMEGA Studio — Agent Skills Hub v2.1.0

## 11 źródeł

Przypięte rewizje i licencje: [config/skills_sources.lock.json](../config/skills_sources.lock.json).

Źródła: mattpocock/skills, anthropics/skills, emilkowalski/skills, vercel-labs/skills, openai/skills, google/skills, huggingface/skills, mojealterego/awesome-agent-skills, mojealterego/science-skills, obra/superpowers, nextlevelbuilder/ui-ux-pro-max-skill.

OpenAI/skills oznacza repozytorium deprecated z licencjami poszczególnych Skills. Anthropic/skills także wymaga kontroli licencji indywidualnych plików. Vercel-labs/skills to przede wszystkim CLI, a awesome-agent-skills to katalog odnośników; nie należy utożsamiać listy repozytoriów z liczbą lokalnie zainstalowanych Skills.

## Funkcjonalność zaimplementowana i testowana w pakiecie źródłowym

- `omega_actions.ultimate.skills_hub.SkillHub`: import ZIP z limitami, kontrola ZipSlip/symlinków/duplikatów, indeks `SKILL.md`, wersjonowanie SHA-256, wyszukiwanie, odczyt zasobów, składanie kontekstu
- `omega_actions.ultimate.skills_cli`: `sources`, `import`, `sync`, `search`, `show`, `compose`
- `/api/ultimate/skills/*`: źródła, wyszukiwanie, import, sync, szczegóły, kontekst
- `/api/providers/chat`: wybór do czterech Skills i przekazanie ich do rzeczywistego lokalnego LLM
- `/skills`: przeglądarkowy interfejs premium
- Android Java `SkillArchiveManager`: offline ZIP, przeglądanie i dołączanie instrukcji do wiadomości Chat

Żaden skrypt upstream nie jest automatycznie wykonywany. Pobieranie źródeł wymaga jawnej zgody. Lokalny import ZIP nie potwierdza tożsamości commitu Git; przypięty URL HTTPS nie stanowi niezależnego dowodu obiektu Git.

## Weryfikacja

236 testów Python PASS, 4 podtesty PASS, 19 testów JavaScript PASS; 13 plików Java skompilowanych ze stubami; test JVM importer ZIP PASS; real HTTP i Chromium desktop/mobile PASS (przeglądarka używa kontrolowanego mocka fetch ze względu na politykę sieci).

## Android

Pełny APK z Termux/Python/Git/llama.cpp/code-server wymaga rzeczywistych binariów ARM64, Android SDK, podpisu wydania i testów urządzeniowych. Wersja źródłowa nie zastępuje produkcyjnego APK. Testy symulacyjne nie są certyfikacją urządzenia.

## CI/CD

Nie uruchamiać płatnych GitHub Actions. Commity projektu powinny zawierać `[skip ci] [skip actions]`. Repozytorium Digital-Life pozostaje nienaruszone.
