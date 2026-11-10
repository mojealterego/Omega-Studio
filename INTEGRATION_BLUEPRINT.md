# Integration Blueprint — wyłącznie opis przyszłego połączenia

## Architektura adaptera

```text
OMEGA Ultimate  -- authenticated local transport -->  Digital-Life Gateway
    │                                                   │
    ├─ repo catalog JSON                                 ├─ tenant policy
    ├─ workflow job event                                ├─ capability registry
    ├─ GGUF manifest + digest                            ├─ model runner
    ├─ asset manifest                                    ├─ storage/CAS
    └─ signed AST seal                                   └─ verifier/audit
```

## Kontrakt wiadomości

```json
{
  "protocol": "omega-ultimate/v1",
  "request_id": "e0c4b6d2-4b20-4d48-89bb-05c01e600123",
  "tenant_id": "local-user",
  "operation": "asset.inspect",
  "payload": {"path": "models/model.gguf", "sha256": "<sha256-hex>"},
  "policy": {"network": false, "write": false, "max_bytes": 1048576}
}
```

Powyższy JSON jest przykładowym kontraktem, nie istniejącym publicznym endpointem Digital-Life. Wszystkie ścieżki muszą być rozwiązywane po stronie odbiorcy względem jego własnego katalogu. Identyfikator tenant i uprawnienia nie mogą być przyjmowane na wiarę z treści wiadomości.

## Etapy projektowe

1. Odczyt kontraktów Digital-Life w trybie read-only i porównanie wersji.
2. Uzgodnienie JSON Schema / Protobuf, semantyki błędów i timeoutów.
3. Wymiana jedynie identyfikatorów zasobów oraz sum SHA-256, bez przekazywania sekretów.
4. Walidacja izolacji tenantów i testy migracji w kopii danych, nie na repozytorium produkcyjnym.
5. Jawna autoryzacja właściciela przed ewentualnym połączeniem środowisk.

Nie uruchomiono żadnego z tych etapów jako operacji na istniejącym repozytorium. Ten dokument jest kontraktem projektowym dla przyszłego procesu.

## Zgodność danych

Wymagane: identyfikatory operacji, idempotency key, monotoniczny numer wersji, znacznik źródła, polityka retention i schema digest. Dla strumieni binarnych: bounded chunk, backpressure, checksum, atomic commit. Dla agentów: maksymalna liczba prób, maksymalny koszt i wyraźny verifier. Dla CI: jawny executor, brak domyślnego dostępu do sieci i brak nieautoryzowanych publikacji.


## Rozszerzenie v2.0.0 — weryfikowalny zakres

Szczegółowa macierz wymagań stron 1–11: `docs/MCODE_11_PAGE_TRACEABILITY.md`. Moduły E–H mają klasyczne, deterministyczne implementacje o ograniczonych zasobach; nie deklaruje się fizycznej przewagi kwantowej, zerowej latencji ani nieskończonej skalowalności. Dołączony ELF ARM64 jest rzeczywistym małym modułem diagnostycznym, a nie zamiennikiem Termux. Oryginalne archiwa dostarczone przez użytkownika opisuje `docs/UPLOADED_SOURCE_AUDIT.md`.
