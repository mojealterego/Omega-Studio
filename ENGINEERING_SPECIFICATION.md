# Specyfikacja inżynieryjna i matematyczna

## 1. Bounded Memory-Mapped Streamer

Dla pliku o rozmiarze `N` i okna `W` (`4 KiB ≤ W ≤ 64 MiB`) `WindowedReader.read_at(offset,length)` mapuje zakres od granicy strony systemowej `P` do `length+P`. Maksymalny rozmiar pojedynczego mapowania: `W+P`. Złożoność pamięci **O(W)**, a dla stałego `W` niezależna od `N` (potocznie O(1) względem wielkości pliku). Pełny SHA-256 wymaga czasu O(N) i odczytu całego pliku. `copy_file` wykorzystuje `os.sendfile` na obsługiwanych platformach i porównuje SHA-256 źródła oraz pliku tymczasowego przed atomowym `os.replace`. Nie istnieje fizycznie zerowy czas dostępu do danych na nośniku.

## 2. Konserwatywna dyfuzja grafowa roju

Dla krawędzi `(i,j)` i pojemności `c_i>0` obliczana jest presja `p = L_i/c_i - L_j/c_j`. Transfer `δ = clamp(ηp, -L_j, L_i)` dla `0<η≤0.5`. Aktualizacja `L_i ← L_i-δ`, `L_j ← L_j+δ` zachowuje `ΣL_i` i `L_i≥0`. Heurystyka nie jest fizycznym rozwiązaniem przepływu Ricciego, a nazwa „Ricci” w specyfikacji jest inspiracją, nie twierdzeniem o własnościach krzywizny.

`SwarmCoordinator` utrzymuje `max_workers≤64`, `max_pending≤4096`, odbiera wyniki w kolejności wejściowej. `DuoCoordinator` wykonuje `1..32` prób, a niezaliczone wyniki kończą się wyjątkiem. To deterministyczna kontrola budżetu, nie samoreplikacja agentów.

## 3. TRS-SEAL

Dla drzewa składniowego Pythona `G=(V,E)`:

- `χ = |V| - |E|` — charakterystyka Eulera grafu.
- `β₁ = |E| - |V| + C` — liczba niezależnych cykli w grafie nieskierowanym o `C` składowych.
- Kanoniczny AST = `ast.dump(..., include_attributes=False)`; dodatkowo SHA-256 pełnych bajtów źródła.
- HMAC-SHA3-256 z niezależnym sekretem obejmuje wersję, obydwa skróty i metryki grafu.

Pieczęć wykrywa modyfikacje, nie dowodzi semantycznej poprawności, bezpieczeństwa programu ani zgodności języka innego niż Python.

## 4. Kryptografia

Istniejący `SecretVault` stosuje `Argon2id(time_cost=3,memory_cost=65536 KiB,parallelism=2)`, 64 bajty materiału kluczowego, AES-256-GCM (losowy nonce 96 bitów), HMAC-SHA3-256, losowy salt 128 bitów i atomowy zapis z uprawnieniami 0600. HMAC uwierzytelnia kopertę, a AES-GCM zapewnia poufność i integralność AEAD. Stała φ i linia krytyczna ζ nie zapewniają dodatkowej entropii kryptograficznej; nie używa się ich jako zamiennika standardowych prymitywów.

## 5. ZIP/RAR

ZIP64 z deterministycznymi timestampami; ekstrakcja do staging, walidacja ścieżek, specjalnych plików, duplikatów, liczby plików, limitu bajtów i stosunku dekompresji. RAR wymaga `rarfile` + lokalnego dekodera dla skompresowanych wpisów; tworzenie RAR wymaga licencjonowanego programu `rar`. Nie jest deklarowana zgodność ze wszystkimi wariantami RAR5.

## 6. Crawler i chmura

GitHub `per_page≤100`, `pages≤1000`, domyślnie 20. Błąd 403/429 z wyczerpanym limitem jest jawny; brak automatycznego obchodzenia limitów. Pobranie archiwum ograniczone do `codeload.github.com` i SHA-1 commita o 40 znakach. GitLab, HF, Drive korzystają z ustalonych hostów HTTPS. Dostęp do Drive wymaga tokenu OAuth z prawami użytkownika.

## 7. Dostęp zdalny

Loopback HTTP 8080 lub TLS dla innych adresów. Basic auth używa porównania stałoczasowego, a WebSocket sprawdza Authorization przed akceptacją. Operacje plikowe są ograniczone do katalogu root, do tekstu UTF-8 do 1 MiB; zapis atomowy, kontrola wersji SHA-256. System plików lokalny pozostaje zaufaną granicą procesu; brak izolacji od innych procesów tego samego użytkownika.

## 8. Symulacje

Stałe ziarno PRNG, deterministyczny mock HTTP 20 stron, GGUF v3 header, DAG 2 jobów, pula agentów, graf obciążeń, auth HTTP, archiwum, HMAC AST i istniejący dyskretny bliźniak infrastruktury. Symulacja weryfikuje kontrakty, nie zastępuje fizycznego Android/ARM64, prawdziwego ruchu WAN ani niezależnego audytu.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
