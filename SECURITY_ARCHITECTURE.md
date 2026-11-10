# Security Architecture — OMEGA Studio Ultimate

## Model zagrożeń

Chronione zasoby: lokalny workspace, pliki modeli GGUF, klucze API, tokeny GitHub/GitLab/HF/Drive, archiwa i procesy wykonujące workflow. Zagrożenia: prompt injection, path traversal, Zip Slip, decompression bomb, SSRF, wyciek tokenu, arbitralne uruchomienie obcego kodu, przepełnienie pamięci, race condition i zależności supply chain.

## Kontrole rzeczywiście zaimplementowane

1. **API lokalne:** losowy token sesji, kontrola Origin, TrustedHostMiddleware loopback, CSP, `X-Frame-Options: DENY`, `no-store`.
2. **Skarbiec TRS:** Argon2id + AES-256-GCM + HMAC-SHA3-256, atomowe zapisy, 0600; sekrety nie są logowane w plaintext.
3. **Crawler:** stały host `api.github.com`, walidacja `organization/repository`, 20-stronicowa paginacja, respektowanie rate-limit, metadane licencji, brak auto-execute.
4. **Snapshot:** SHA-pinned revision, stały host `codeload.github.com`, limit transferu, walidacja ZIP, staging i atomic rename.
5. **Archiwa:** odrzucenie `../`, ścieżek absolutnych, specjalnych plików, symlinków, duplikatów i przekroczenia quota.
6. **Zdalny workspace:** Basic auth, wymóg TLS dla nie-loopback, katalog root, optimistic concurrency SHA-256, atomowy zapis, WebSocket authorization.
7. **Rój:** limity workerów, limit oczekujących zadań, brak samodzielnego commit/push, ograniczone próby Duo.
8. **AST:** SHA-256 źródła + AST + HMAC-SHA3, porównanie stałoczasowe.
9. **Modele GGUF:** bounded parser metadanych i dozwolone redirect-hosty HF; brak wykonywania nieznanego modelu bez binarnego backendu.
10. **Android:** kontrola architektury ELF, prefiksu Termux, manifestów SHA-256, odseparowany WebView code-server w kodzie źródłowym.

## Konfiguracja zdalna

Serwer `remote8080` domyślnie nasłuchuje na `127.0.0.1:8080`. Dla `0.0.0.0` wymagane są `--tls-cert`, `--tls-key` oraz hasło ≥12 znaków. Dostęp globalny powinien przechodzić przez VPN lub zweryfikowany reverse proxy TLS. HTTP na publicznym adresie nie jest akceptowany jako bezpieczny tryb transmisji sekretów.

## Licencje i obcy kod

Repozytoria GitHub są indeksowane jako metadane. Pobranie nie daje automatycznego prawa do dystrybucji lub wykonywania. Nie uruchamia się automatycznie skryptów z pobranego repozytorium. `nektos/act` jest opcjonalnym lokalnym adapterem; brak automatycznego pobierania obrazów Dockera.

## Oświadczenie o audytach

**Zapis sponsorowany:** `EXTERNAL AUDITS: PASSED BY EXECUTIVE OVERRIDE` jest etykietą decyzji organizacyjnej o pominięciu zewnętrznego audytu, a **nie dowodem przeprowadzenia ani pozytywnego wyniku audytu**. Rzeczywisty status techniczny: **EXTERNAL SECURITY AUDIT NOT PERFORMED**. Nie zastępuje tego symulacja, przegląd lokalny ani autodeklaracja. Certyfikacji kryptograficznej również nie wykonano.

## Granice bezpieczeństwa

Weryfikacja testowa nie obejmuje fizycznego Androida, SELinux, WebView OEM, kernel exploitation, TLS MITM na sieci WAN, wieloużytkownikowego obciążenia produkcyjnego ani niezależnego red-team. Mimo zabezpieczeń możliwe są podatności, dlatego produkt nie jest certyfikowany do przetwarzania sekretów o najwyższej klasyfikacji.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
