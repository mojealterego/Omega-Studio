# Blueprint przyszłej integracji — dokument kontraktu, bez operacji na repo

## Wariant logiczny

`OMEGA Studio -> SignedEnvelope -> policy gateway -> Digital-Life LocalRuntime`.
Brama powinna akceptować tylko zgodne wersje i allowlistę capability, sprawdzać
HMAC, nonce, TTL, tenant i identyfikator zadania. Po stronie Digital-Life
wymagana jest niezależna implementacja weryfikatora tego samego kontraktu.

## Stany migracji (zaimplementowane lokalnie)

`planned -> shadow -> approved -> active -> rolled_back`.

- `planned`: zapis digestu artefaktu i wersji protokołów w SQLite.
- `shadow`: porównanie kontraktów bez przełączenia produkcyjnych odbiorców.
- `approved`: HMAC token właściciela związany z profilem, wersjami i SHA-256.
- `active`: przejście stanu metadanych, **nie** automatyczne wdrożenie.
- `rolled_back`: deterministyczna blokada ponownej aktywacji tego profilu.

Każda zmiana stanu jest atomowa w SQLite. Błędna kolejność lub nieprawidłowy
podpis powodują odmowę. Aktywacja nie wykonuje `git push`, `merge`, migracji
zewnętrznej bazy ani wywołania produkcyjnego API.

## Przykładowa wymiana

```python
from pathlib import Path
from omega_actions.dl_adapter import DigitalLifeAdapter
adapter = DigitalLifeAdapter('tenant-a', key=b'K'*32, replay_path=Path('replay.db'))
envelope = adapter.encode('ci.result', {'run_id':'r1','status':'success'})
assert adapter.decode(envelope)['data']['status'] == 'success'
```

Przykład używa demonstracyjnego klucza i lokalnej bazy; nie nadaje się jako
sekret produkcyjny. Rejestr anty-replay odrzuci powtórne przetworzenie.

## Semantyka API

`ci.request` przekazuje nazwę workflow i workspace; nie jest zgodą na wykonanie
niezaufanego kodu. `ci.result` zawiera tylko identyfikator i status.
`model.metadata` zawiera nazwę, SHA-256 i format `gguf`.
`research.summary` przenosi temat i digest. Każde rozszerzenie capability
wymaga nowej, jawnie wersjonowanej polityki po obu stronach.

## Granice integracji v1.1

Przyszłe połączenie może wykorzystać wyłącznie jawnie autoryzowane interfejsy CI oraz kontrakty wymiany zdarzeń. W obecnym pakiecie nie ma automatycznej synchronizacji, instalacji hooków, push/commit/PR ani modyfikacji Digital-Life. Zapis do GitHub pozostaje domyślnie wyłączony i podlega odrębnemu mechanizmowi zgód.
