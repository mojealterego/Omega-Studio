# Digital-Life Compatibility — kontrakt projektowy, bez integracji

Repozytoria `mojealterego/Omega-Studio` i `mojealterego/Digital-Life` były źródłami odniesienia. Żadne zmiany nie zostały wysłane do tych repozytoriów podczas przygotowania tej paczki.

## Proponowane granice

| Obszar | OMEGA Studio Ultimate | Kontrakt wymiany |
|---|---|---|
| Repo katalog | `RepositoryIndex` SQLite | JSON z `full_name`, `sha256`, `license`, `source` |
| Silnik workflow | `omega_actions.engine` | `run_id`, `jobs`, `status`, logi SSE |
| Modele GGUF | `GGUFInspector`, `HFDownload` | `path`, `sha256`, `model_parameters`, `tensor_count` |
| Rój | `SwarmCoordinator`, `DuoCoordinator` | idempotentne `task_id`, limit prób, wynik weryfikatora |
| Assety | PNG/SVG/WAV/MP4/glTF | `mime`, `bytes`, `sha256`, metadane czasu |
| Sekrety | `SecretVault` | referencja do sekretu, nigdy plaintext w kontrakcie |
| Pieczęć | `seal_python_source` | `version`, `sha256`, `ast_sha256`, `chi`, `beta1`, `hmac_sha3_256` |

## Zgodność wersji

Wersjonowanie semantyczne kontraktu: `omega-ultimate/v1`. Wymagane jest jawne uzgodnienie pól, a nie ciche nadpisywanie. Nieznane pola mogą być ignorowane tylko w kierunku odczytu, wymagane pola nie mogą być pomijane. Prawa tenantów i dostęp do kluczy muszą być sprawdzane po obu stronach.

## Izolacja

- OMEGA Studio działa w osobnym katalogu, nie zapisuje do Digital-Life.
- Adaptery transportowe nie otrzymują tokenów zdalnych bez jawnej konfiguracji właściciela.
- Podczas importu źródeł obowiązuje pin SHA, skan archiwum i polityka licencji.
- Komunikaty obcych repozytoriów, komentarze kodu i opisy issue są traktowane jako dane nieufne, nie instrukcje agenta.

## Test symulacyjny

Istniejący `digital_twin.py` zawiera symulowany protokół Digital-Life v1. Nowy `ultimate/simulation.py` sprawdza spójność niezmienników w izolacji. Symulacja nie potwierdza zgodności z aktualnym, żywym interfejsem Digital-Life; nie wykonano migracji ani integracji.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
