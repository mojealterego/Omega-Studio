# MCode.pdf — macierz śledzenia wymagań (11 stron)

Źródło: `reference/MCode.pdf` (11 stron, odczyt 2026-11-10). Rozdzielono działający kod, symulację i testy urządzeniowe. Nie stosuje się fikcyjnych zaliczeń audytu.

| Strona | Wymaganie źródłowe | Implementacja w pakiecie | Dowód / granica |
|---|---|---|---|
| 1 | VS Code v1.85.1 Android/Desktop, GitHub/GitLab, CI/CD, NoCode, GGUF, API | `android/`, `backend/omega_actions/`, `builder/`, `tools/` | istniejące testy hostowe; pełna zgodność VS Code 1.85.1 i Android IDE nie została wykazana |
| 2 | debugowanie, podświetlanie, Git, fullscreen, port 8080 | `CodeEditorActivity.java`, `CodeServerManager.java`, `ultimate/remote8080.py` | testy HTTP/WebSocket; fizyczny Android i code-server wymagają działającego runtime |
| 3 | IntelliSense, snippets, refactoring, Git, skróty | źródła Code-OSS 1.85.1 przypięte w `config/upstream_sources.lock.json`; edytor HTTP | nie jest to pełny zintegrowany VS Code; źródła dostarczone przez użytkownika to Code-OSS 1.143.0 |
| 4 | multi-cursor, terminal, split-screen, task manager, workspaces | `android/`, `backend/omega_actions/ultimate/remote_ide.html` | częściowa funkcjonalność lokalnego edytora, bez dowodu parytetu 1.85.1 |
| 5 | 170+ języków, NoCode chat, nieograniczone pliki, ZIP/RAR, multimodal 2D–4D, Chat Leak/Duo | `builder/`, `ultimate/streamer.py`, `archives.py`, `assets.py`, `swarm.py`, `code_swarm.py` | generator proceduralny i analiza statyczna; brak nieograniczonej pojemności nośnika i pełnej generatywnej multimodalności |
| 6 | Własne Actions, GitHub/GitLab/HF/Drive, mmap, AST repair, TRS Vault | `backend/omega_actions/`, `ultimate/crawler.py`, `streamer.py`, `self_healing_ast.py`, `vault.py` | testy integracyjne hostowe; samonaprawa celowo ograniczona do bezpiecznych poprawek |
| 7 | symulacja sieci, Quantum-Topological AST | `ultimate/network_chaos.py`, `quantum_topology.py` | deterministyczna symulacja i klasyczne wektory zespolone, bez urządzenia kwantowego i bez dowodu wykrywania wszystkich luk |
| 8 | Holographic Memory Weaver, Self-Evolving CI, Neuromorphic Synapse | `ultimate/holographic_memory.py`, `adaptive_ci.py`, `neuromorphic_synapse.py` | dyskowy indeks bloków, podpisane plany operatora, ograniczone STDP; bez zerowej latencji i autonomicznego wdrażania |
| 9 | Chat Leak/Duo, strony GitHub 1–6 | `ultimate/swarm.py`, `config/organization_sources.json`, `crawler.py` | test MockTransport i baza SQLite; nie jest to pobranie wszystkich projektów |
| 10 | strony GitHub 7–14 | `config/organization_sources.json`, `crawler.py` | symulacja 20 kolejnych stron PASS; aktualne API GitHub może zwrócić mniej stron |
| 11 | strony GitHub 15–20 | `config/organization_sources.json`, `crawler.py` | j.w. |

## Kryteria fizycznego wydania Android

Wersja APK w `dist/` jest podpisanym podglądem, zawierającym prawdziwy ELF64 AArch64 `libomega_runtime.so` (CRC32 i kontrola nagłówka GGUF). Nie zawiera pełnego bootstrap Termux, CPython, Git, llama.cpp ani code-server. Kompilacja pełnego projektu Android Studio, instalacja i wykonanie na telefonie nie były częścią testów wykonanych w tej sesji. `tools/verify_android_apk_release.py` sprawdza kompletne binaria i nie przyjmuje podglądu jako wydania produkcyjnego.

## Granice matematyczne i bezpieczeństwa

`O(1)` dotyczy ustalonego maksymalnego rozmiaru bufora przy przetwarzaniu strumieniowym; nie dotyczy łącznej pamięci potrzebnej do zindeksowania danych ani rozmiaru wyjścia. Dostęp do nośnika ma niezerową latencję. Złoty podział i linia krytyczna nie są algorytmami kryptograficznymi. AES-256-GCM + Argon2id i HMAC-SHA3-256 zapewniają konkretne, testowalne właściwości, ale nie gwarantują bezpieczeństwa po kompromitacji procesu lub urządzenia. Przestrzeń Hilberta w module AST to klasyczny model matematyczny, nie procesor kwantowy. Symulacje nie zastępują audytu, badań na urządzeniu ani formalnej weryfikacji.
