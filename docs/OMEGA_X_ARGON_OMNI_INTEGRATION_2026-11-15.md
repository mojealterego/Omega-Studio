# OMEGA Studio — integracja OMEGA-X / ARGON / OMEGA OMNI (15.11.2026)

## Zakres i baza zmian

Repozytorium docelowe: `mojealterego/Omega-Studio`, gałąź `main`. Integracja rozszerza istniejące `docs/GEODEPTH_OCG_ARGON_BATCH1.md`, `docs/OMEGA_BATCH2_SAFETENSORS_VIRTUAL_COMPUTE_AETHEROMNI.md`, `backend/omega_actions/ultimate/safetensors_guard.py`, `backend/omega_actions/ultimate/agent_dag.py` oraz `backend/omega_actions/audit_ledger.py`. Nie powiela tych komponentów. Niniejsza partia **nie** obejmuje zapisu do `ocaf-runtime`, trenowania fundamentów ani budowy nowej dystrybucji Android.

## Zweryfikowany nowy komponent

`backend/omega_actions/ultimate/pareto_checkpoint.py` — odczytowy audyt adaptera LoRA, wywołujący dotychczasowy walidator `safetensors_guard` z obliczeniem SHA-256.

- Wymusza kompletne pary `lora_A.weight` / `lora_B.weight`, wymiary 2D, dodatni wspólny rank oraz deterministyczne porządkowanie.
- Ustala docelowy kształt macierzy bazowej bez ładowania lub zmiany checkpointu.
- Zgłasza różne dtypes, brak `lora_alpha`, brak identyfikatora bazowego modelu, brak hasha.
- Rozróżnia `omega.source_sha256` (źródło adaptera) od `base_model_sha256` (wymagana tożsamość bazowego modelu). Nigdy nie utożsamia tych pól.
- Opcjonalny kontrakt sprawdza dopasowanie rozmiarów warstw, deklarowanego i zmierzonego SHA-256, skalowania i licencji. Wynik `CONTRACT_MATCH_ONLY` nie jest dowodem inferencji, zgodności jakości ani produkcji.
- Nie wykonuje trwałego `weight baking`, abliteracji, fuzji, konwersji typów, generowania obrazu i wideo; `eligible_for_automatic_merge=False` zawsze.

CLI: `PYTHONPATH=backend python3 -m omega_actions.ultimate.pareto_checkpoint /path/model.safetensors --output audit.json` (tworzy nowy plik; nie nadpisuje checkpointu).

## Wynik rzeczywistego wejścia OMEGA_OMNI_v6_PARETO_RELAY.safetensors

- Rozmiar 4 774 032 bajtów, SHA-256 `1b308e1a386100c7395384219054c2273127964aeec45e4abf4c244ff789ef8d`.
- Poprawny kontener: 288 tensorów / 144 kompletne pary LoRA, rank = 1.
- 94 pary wymagają jawnego ujednolicenia typu (F16/F32); pozostałe 50 są zgodne typowo.
- Metadane: `omega.version=4.0.0`, `omega.mode=frontier`, `omega.source_sha256=424be9ca...`, Pareto budgets.
- Brak `base_model_sha256` i `lora_alpha`: **merge BLOCKED**. Nie ma dowodu, że adapter przejdzie inferencję z dowolnym modelem bazowym.

## Macierz selekcji dokumentów dostarczonych w partiach

| Materiał | Co wykorzystujemy | Czego nie przyjmujemy za udowodnione |
|---|---|---|
| OMEGA-X v25–v28, PDF 21/41/59 stron | typowany DAG/AoT, separacja stanu D od promptu, budżety, wersjonowanie CAS, epistemiczna proweniencja, niezależny verifier, polityki, warunki rollback | 315/9999 agentów i 3,784 ms jako benchmark OMEGA Studio; kwantowe/fotoniczne hardware mobilne |
| ARGON-OMEGA, 20 stron | walidacja LoRA/PRISM jako artefaktu, idea RIFLEx i kafelkowania do późniejszych eksperymentów, zarządzanie pamięcią i konfiguracją | beztreningowy ogólny cross-model merge, 8K wideo lokalnie na S24, brak utraty jakości po ORBA/Apostate |
| KREA2 / tensor restoration | integralność SafeTensors, odczyt bez pickle, SHA-256, niezależny kontrakt par | rekonstrukcja przypadkowych wag z tekstu, dithering jako odzyskanie informacji |
| AetherOmni-Core / 400 MP | ROI/halo/dirty regions, out-of-core planner, budżety pamięci, precyzyjna kalibracja, zachowanie RAW | wirtualna bezkosztowa pamięć, 1 Gpx 60 fps bez sprzętu |
| OCAF GeoDepth Ω | optical depth vs ray range, WGS84, SE(3), kalibracja i pochodzenie jednostek | centymetrowa metryka z pojedynczego nieskalibrowanego zdjęcia |
| OCG / cinematic | wymierna oś czasu PTS, uprawnienia, deterministyczny eksport, kontrole zgód | automatyczna kompatybilność dowolnych generatorów i ścieżek AV |
| AETHERIS Ω-VAE | kafelkowane kodowanie/dekodowanie, kontrola halo, jawne VAE weights/model ABI | autorskie wytrenowane generatywne VAE bez danych/weights i testów |
| ArcFace Ω / CodeFormer Ω | kontrola wierności twarzy i detale odtwarzania, identyfikacja w kontekście wyraźnej zgody | zweryfikowany embedding/wagi i działanie na S24 bez testów; fałszywy test biometryczny |
| V-JEPA / SAE / Titans | reprezentacja czasowa i pamięć jako kierunek eksperymentów | ukończony trening JEPA/SAE i biologiczne/świadomościowe twierdzenia |
| Wirtualny CUDA/GPU/NPU, Ryzen-Core | profiling, CPU fallback, kwantyzacja, streaming; poprawna abstrakcja CPU/GPU | przekształcenie CPU/Android w natywną CUDA/Hopper lub sprzęt AMD/Intel |

## 18 filarów OMEGA-X — decyzja

**P0 (już częściowo obecne, wzmacniać):** I AoT/DAG; II autorytatywny stan i uprawnienia; IV niezależna weryfikacja i anti-vacuity; V pamięć temporalna/proweniencja; IX monitoring ryzyka i anytime-valid checks w jawnych, testowalnych kontraktach.

**P1 (adaptery eksperymentalne):** III samooptymalizacja z izolacją ewaluatora; VI pomiarowo sterowany scheduler; VII jawne stany na granicy latent/symbolic (tylko jeśli zgodny model); XI bounded memory; XIV ograniczona koordynacja, bez nieograniczonych rojów; XVIII przydział zasobów według zaobserwowanego kosztu, nie deklarowanej DSIC.

**Serwer / badania:** VIII rozproszony KV/prefill; X sprzętowe TEE; XII GPU-initiated networking; XIII zkVM; XV fotonika/CXL; XVI wafer-scale/neuromorfika; XVII qLDPC kwantowe; całość opcjonalna, bez blokowania Android.

## Powiązania z już istniejącym kodem

- `ultimate/agent_dag.py`: zależności, limity równoległości, zakaz możliwości nieautoryzowanych. Nie tworzyć drugiego planera.
- `audit_ledger.py`: HMAC-SHA256 i SQLite WAL. Nie nazywać tego dowodem blockchain ani sprzętową atestacją.
- `ultimate/safetensors_guard.py`: bezpieczeństwo kontenera, nowy `pareto_checkpoint.py`: kontrakt adaptera i modelu bazowego.
- `ultimate/mobile_tile_planner.py` i `ultimate/geodepth_contract.py`: realne ograniczenia RAM, ROI i kalibracja.
- `ultimate/cinematic_timebase.py`: wymierny czas filmu i audio.

## Testy i kryteria integracji

- Nowe testy: `tests/ultimate/test_pareto_checkpoint.py`; lokalnie 10/10 PASS Python 3.13, test binarnego SafeTensors i przypadków błędnych. Kompilacja Python: PASS.
- Audyt rzeczywistego PARETO_RELAY: PASS strukturalnie, **FAILED release gate** z powodu braku bazy/alpha i mieszanych typów.
- Nie wykonano E2E inferencji generatywnej, testów GPU Adreno/QNN, natywnej kompilacji Android, testu termicznego ani podpisania APK.
- 8K to w tym stanie wyłącznie docelowy format eksportu/strumieniowania, nie potwierdzone generowanie 8K na S24.

## Kolejność kolejnego domknięcia

1. Pozyskać jednoznaczny, licencjonowany model bazowy: architekturę, manifest tensorów, SHA-256 i `lora_alpha` dla v6 PARETO.
2. Uruchomić kontrakt warstw i konwersję dtypes w izolowanej kopii, bez nadpisywania źródła.
3. Wykonać deterministyczne próby generatywne na zestawie held-out, mierząc drift, jakość i wpływ na resztę modelu.
4. Uruchomić fizyczny Android S24 Ultra: RSS, P50/P95, termika, QNN/GPU fallback, crash recovery.
5. Dopiero później przygotować nowy zreprodukowalny ZIP/APK i dowód wdrożenia.

Dokument rozróżnia źródła, testy syntetyczne, dowody lokalne oraz sprzętowe. Liczby cytowane z PDF-ów nie są automatycznie benchmarkami projektu.