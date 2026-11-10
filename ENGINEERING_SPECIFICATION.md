# Specyfikacja inżynieryjna i niezmienniki

## Retry, obwód awaryjny i obserwowalność

`RetryPolicy` stosuje ograniczoną liczbę prób `1 <= N <= 100`. Dla kolejnego opóźnienia
`i=0..N-2`:

\[
 d_i = \min(d_{max}, \min(d_{max},d_0 2^i) \cdot (1-J/2+J U_i)), \quad U_i \in [0,1).
\]

`U_i` jest deterministycznie generowane przez `random.Random(seed)` w testach; produkcyjne
użycie nie powinno polegać na przewidywalności jittera jako zabezpieczeniu kryptograficznym.
`AdaptiveCircuitBreaker` implementuje `closed -> open -> half_open -> closed/open`,
z pojedynczą próbą w stanie half-open, zegarem monotonicznym i blokadą `threading.Lock`.
Nie jest to struktura lock-free ani twarda gwarancja czasu rzeczywistego.

`LatencyTelemetry` utrzymuje dla każdego klucza `deque(maxlen=capacity)` i licznik całkowity.
Percentyle liczone są metodą nearest-rank dla **próbek z okna**; pamięć jest ograniczona
przez `capacity` dla każdego klucza. Brak gwarancji sub-millisecond tail latency.

## Trwałość i integralność

`DurableLeaseQueue` wykorzystuje SQLite `BEGIN IMMEDIATE` do atomowego `claim` i `recover`.
Własność: `attempts <= max_attempts`; zakończenie wymaga aktualnego właściciela i
niewygasłej dzierżawy. Model jest **at-least-once**, a nie exactly-once dla efektów zewnętrznych.
Dla operacji z efektami ubocznymi odbiorca musi stosować klucz idempotencji.

Łańcuch audytu:

\[
 h_i = \operatorname{HMAC}_{SHA256}(K,\operatorname{CanonicalJSON}(i,event,payload,t, h_{i-1})).
\]

Klucz 256-bit jest generowany lokalnie z uprawnieniami 0600. Weryfikator wykrywa zmianę
zawartości i kolejności rekordów; bez zewnętrznego zakotwiczenia głowy łańcucha
nie wykryje usunięcia całej bazy i klucza przez napastnika z pełną kontrolą hosta.

## Kontrakt Digital-Life

Protokół `1.0`, kanoniczny JSON UTF-8, `tenant`, `kind`, `nonce` (128-bit),
`issued_at`, `expires_at`, `payload`, `signature` (HMAC-SHA256). `MAX_PAYLOAD=256 KiB`,
`MAX_TTL=600 s`; okno dopuszczalnego przesunięcia zegara 30 s. Anty-replay:
SQLite `UNIQUE(tenant,nonce)` i kontrola czasu ważności.

## Symulator

Ziarno determinuje losowanie opóźnień, awarii workerów i błędów sieci. Zdarzenia
`start/finish` uporządkowane są w kopcu `(czas,seq,typ,job)`. `worker_count` ogranicza
współbieżność; liczba prób wynosi maksymalnie 4, a budżet zdarzeń maksymalnie `30*jobs`.
Niezmienniki: brak podwójnego efektu, skończone retry, pusty backlog, bounded parallelism,
liczba odzyskanych dzierżaw nie większa od liczby awarii workerów.

## Ograniczenia wejścia

GGUF v2/v3: limit metadanych 8 MiB, do 100 000 kluczy, długość stringa do 1 MiB.
HF: do 50 GiB na model, kontrola hostów HTTPS, zakresów HTTP i opcjonalny SHA-256.
GitHub: walidowane `owner/name`, branch `omega/*`, jawne allowlisty i planowanie zmian.
Przyspieszenia GPU/NPU i realna przepustowość Android nie były mierzone.

## Inwarianty v1.1

1. Żaden zewnętrzny provider nie zostanie wywołany bez jednoczesnego `OMEGA_ENABLE_PAID_AI=true` oraz `confirm_cost=true` w backendzie.
2. URL dostawcy pochodzi z wbudowanego katalogu 24 usług; brak dowolnego adresu z żądania użytkownika; przekierowania HTTP nie są śledzone.
3. Token nie jest przekazywany do JS ani do URL query; w wynikach i błędach gateway nie zwraca nagłówków autoryzacji.
4. Bootstrap musi pasować do prefiksu `/data/data/org.omega.actions/files/usr`, SHA-256 i ELF `e_machine=183` dla wymaganych poleceń.
5. Źródła backendu są rozpakowywane po weryfikacji SHA-256, w prywatnym katalogu, z blokadą zip-slip i limitem rozmiaru.
6. Wykonywanie YAML wymaga zgody operatora i obecności Pythona/Git; nie ma zastępczego wykonania w systemowej powłoce.
