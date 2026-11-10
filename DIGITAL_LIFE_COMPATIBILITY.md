# Digital-Life: zgodność kontraktowa bez integracji

Źródło referencyjne: `mojealterego/Digital-Life`, `README.md` z 2026-11-09,
odczytane bez modyfikacji. Repozytorium opisuje NOEVARIS Ω jako jeden silnik
`IntegratedEngine`, z rozróżnieniem `PRODUCTION_ADMISSION_SIMULATED_ONLY`
od `DEPLOYED` i `PRODUCTION_VERIFIED`. Niniejszy pakiet jest **osobnym artefaktem
przygotowawczym**, nie nowym silnikiem wewnątrz Digital-Life.

## Implementowany kontrakt wymiany

`omega_actions.dl_contract.SignedEnvelope` v1.0 + `ReplayGuard` +
`omega_actions.dl_adapter.DigitalLifeAdapter`:

| Pole | Reguła |
|---|---|
| `version` | `1.0` |
| `tenant` | wymagany identyfikator izolacji |
| `kind` | `omega.studio.exchange.v1` |
| `nonce` | 128-bit hex, unikalny w tenant |
| `issued_at`, `expires_at` | sekundy Unix, TTL maks. 600 s |
| `payload` | max 256 KiB kanonicznego JSON |
| `signature` | HMAC-SHA256 z kluczem właściciela |

Dozwolone możliwości: `ci.request`, `ci.result`, `model.metadata`, `research.summary`.
`DigitalLifeAdapter` odrzuca inne capability, w tym próby `repo.push`.

## Mapa odpowiedzialności

| OMEGA Studio | Potencjalny odbiorca Digital-Life | Granica |
|---|---|---|
| CI result / workflow metadata | warstwa lokalnych zadań | tylko zweryfikowana wiadomość |
| GGUF metadata + SHA-256 | katalog lokalnych modeli | bez wykonywania modelu |
| Research summary digest | indeks wiedzy | digest, nie dowód matematyczny |
| HMAC audit head | archiwum pochodzenia | wymaga odrębnego zaufanego zakotwiczenia |

## Kontrola konfliktów

Brak współdzielenia katalogów runtime, plików stanu i bazy SQLite. Adapter
nie importuje modułów `IntegratedEngine` i nie ingeruje w jego roadmapę.
Migracja jest reprezentowana lokalnym `MigrationJournal`, bez sieci i zapisu do repo.
Testy symulują zgodność formatu i stanu, nie potwierdzają interoperacyjności
z rzeczywistą wersją Digital-Life ani podpisaną migracją produkcyjną.

## v1.1

Rozszerzenia Chat/API i runtime pozostają w osobnym katalogu projektu. Digital-Life nie było używane do testów wykonawczych. Dotychczasowe kontrakty `dl_contract.py`, `dl_adapter.py` i symulacja pozostają bez modyfikacji w repozytorium docelowym. Integracja GitHub pozostaje zgodna z polityką braku zapisów.
