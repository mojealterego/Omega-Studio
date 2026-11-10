# MCode.pdf — matryca zgodności stron 1–11 (OMEGA Studio v2)

**Źródło:** `references/MCode.pdf`, 11 stron, odczyt 2026-11-10. Dokument stanowi opis produktu, a nie kompletną specyfikację protokołów ani algorytmów. Testy jednostkowe nie dowodzą pełnej zgodności produktu z dokumentem.

| Strona | Wymagania z PDF | Istniejący kod / dodatek v2 | Dowód i zakres |
|---|---|---|---|
| 1 | Android VS Code, elastyczna edycja, debugowanie | `android/`, `backend/omega_actions/ultimate/remote8080.py`, `serve.py` | Interfejs przeglądarkowy; brak dowodu parytetu Code-OSS 1.85.1 |
| 2 | Git, rozszerzenia, motywy, fullscreen, :8080 | `android/.../NativeBridge.java`, `CodeServerManager.java`, `remote8080.py` | API i testy hostowe; publiczny HTTP bez TLS nie jest udostępniany |
| 3 | Debugger, syntax highlighting, IntelliSense, snippets, refaktoryzacja | źródła Code-OSS w `third_party/source_archives/vscode-main.zip` | Dostarczony snapshot Code-OSS to **1.143.0**, nie 1.85.1; brak natywnej integracji całego edytora |
| 4 | Multi-cursor, terminal, split screen, zadania, workspaces | `android/app/src/main/assets/`, `backend/omega_actions/ultimate/remote_ide.html` | Funkcje lokalnego edytora, nie pełny runtime VS Code |
| 5 | Ponad 170 języków, NoCode, chat, duże pliki, ZIP/RAR, 2D–4D | `builder/`, `ultimate/assets.py`, `archives.py`, `streamer.py` | Działające podzbiory; liczba 170 języków nie została udowodniona; ZIP działa, RAR zależy od zewnętrznego kodera |
| 6 | Chat Leak/Duo, Własne Actions, GitHub/GitLab/HF/Drive, mmap, AST | `ultimate/swarm.py`, `code_swarm.py`, `crawler.py`, `self_healing.py`, `holographic_memory.py` | Deterministyczne testy; operacje są limitowane i wymagają autoryzacji |
| 7 | TRS Vault, testy sieci, rezonator AST | `vault.py`, `trs_transport.py`, `mobile_network.py`, `quantum_ast.py` | AES-GCM/HKDF i symulacja; brak dowodu przewagi kwantowej |
| 8 | Holograficzna pamięć i autonomiczny CI | `holographic_memory.py`, `ci_singularity.py` | Bounded LRU i podpisywane propozycje; nie ma zerowego czasu I/O ani samowdrożeń |
| 9 | Neuromorficzny rój, początek listy GitHub | `synapse.py`, `crawler.py` | STDP-inspired heurystyka; brak nieograniczonej skalowalności |
| 10 | Organizacja `github`, strony 7–14 | `crawler.py` (`pages=20`), `config/organization_sources.json` | Paginacja wspierana; testy z MockTransport, nie pobrano wszystkich stron w tej sesji |
| 11 | Organizacja `github`, strony 15–20 | `crawler.py` (`pages=20`) | Paginacja wspierana; import repozytoriów wymaga jawnego żądania |

## Uściślenia fizyczne i kryptograficzne

- Wektory zespolone i projekcje w przestrzeni Hilberta są **klasycznymi obliczeniami CPU**. Nie są komputerem kwantowym, nie wykrywają natychmiast wszystkich luk ani nie zastępują testów i analizy statycznej.
- Pamięć podręczna o stałej liczbie bloków ogranicza **użycie pamięci aplikacji**; nie eliminuje opóźnień dysku, transferu, stronicowania ani limitów przestrzeni dyskowej.
- Złoty podział φ i linia krytyczna funkcji zeta **nie są prymitywami kryptograficznymi**. Poufność wynika z Argon2id/AES-GCM/HKDF/HMAC-SHA3-256 i izolacji kluczy, nie z metafory matematycznej.
- Ochrona po naruszeniu transportu zależy od integralności endpointów i tajności kluczy; żaden system nie daje absolutnej gwarancji.
- Autonomiczny CI wymaga autoryzacji, limitów i dowodów. `ci_singularity.py` tworzy wyłącznie weryfikowalne propozycje i nie uruchamia arbitralnego kodu bez zgody.

## Weryfikacja produkcyjna

Bramka APK w `tools/verify_android_apk_release.py` wymaga rzeczywistego bootstrap dla pakietu `org.omega.actions`, podpisu SDK i niezależnych testów urządzenia. Dostarczony plik APK v2 jest **podglądem inżynieryjnym**. Jego biblioteka ELF64 ARM64 jest rzeczywista, ale nie zawiera Termux, Git, Python, llama.cpp ani code-server.
