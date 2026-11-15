# OMEGA Studio — integracja źródeł, partia 1 (2026-11-15)

## Dokumenty wejściowe

1. **Architektura i Wdrożenie GeoDepth Ω.PDF** (80 stron): SYS-AETHERIS-VISION-GEO-003. Kontrakty optycznej głębi Z i odległości wzdłuż promienia ρ, skala względna kontra metryczna, kalibracja K, SE(3), pochodzenie pomiaru, ROI/tiling, rygory licencji i niepewności.
2. **Architektura i Wdrożenie Systemu OCG.PDF** (69 stron): OMEGA-OCG-SPEC-001. Rational Timebase, kanoniczny graf sceny, WorldSnapshot/ScenePlan, Model ABI, deterministyczne DSP, zgody/licencje, profiling Mobile Director.
3. **Architektura Multimodalna Bez Treningu.PDF** (20 stron): ARGON-OMEGA. Fuzja PRISM, GCPA, steering, metody 8K/Video (FreeScale, RIFLEx, FIFO, ParaLin++); materiały badawcze, nie potwierdzone wdrożenie E2E.

## Zakres wdrożony w tej partii

- `backend/omega_actions/ultimate/geodepth_contract.py`: kontrakt geometrii bez zewnętrznych zależności — walidacja jednostek i pochodzenia, rozróżnienie OpticalZ / RayRangeRho, poprawne cofanie rzutowania przy niezerowym skosie K, transformacja K przy ROI+resize z konwencją półpiksela, jawne SE(3) world_to_camera / camera_to_world.
- `backend/omega_actions/ultimate/cinematic_timebase.py`: dokładne obliczanie PTS i przedziałów próbek PCM z ułamków wymiernych; obsługa 30000/1001 i 24000/1001 bez akumulacji dryfu na zaokrąglonych długościach klatki.
- `tests/ultimate/test_geodepth_timebase.py`: testy kontraktów, błędów oraz zamiany układów współrzędnych.

To są **wykonalne biblioteki domenowe**, nie uruchomiony renderer 8K, fotogrametria, kompletny model AV ani gotowe APK. Integracja z zewnętrznym Depth Anything 3, OCG Model ABI i UI wymaga kolejnych adapterów i weryfikacji.

## Krytyczne rozgraniczenia

- W dokumencie GeoDepth symbole T_cw/T_wc stosowane są niejednoznacznie w różnych miejscach; implementacja używa jawnej nazwy **WorldToCameraPose** i testuje obie strony transformacji.
- Wagi CC BY-NC ani pochodne checkpointy nie są automatycznie pobierane, uruchamiane, łączone lub dostarczane. Metadane licencji i zgodności trzeba zweryfikować dla konkretnych wersji z oficjalnych źródeł przed zastosowaniem.
- Z kodu ARGON nie przenosimy jeszcze mutacji checkpointów. Dostarczony opis zawiera błędy składni oraz założenia o konwencjach architektur, kształtach tensorów, skuteczności abliteracji i braku degradacji, które wymagają dedykowanych testów na legalnych, nieprodukcyjnych wagach. Odbicie Householdera zachowuje wartości szczególne samej macierzy, lecz **nie gwarantuje** zachowania jakości/bezpieczeństwa modelu.
- Operacje GCPA/PRISM nie są uniwersalną gwarancją kompatybilności architektur ani zamiennikiem wspólnego treningu. Wydajność 8K na telefonie z 12 GB RAM nie została wykazana.
- Zewnętrzne zasady polityk, zezwoleń, limitów i audytu muszą pozostać oddzielone od modyfikowalnych wag modeli.

## Stan weryfikacji

Testy deterministyczne pytest dla załączonych modułów: **7 passed** lokalnie (Python 3.13); compileall i parser AST: OK. **Nie przeprowadzono** testów urządzenia Samsung, pełnego repozytorium, syntezy generatywnej ani walidacji GPU/VRAM. Repozytorium main pozostaje celem integracji; inne repozytoria są poza zakresem tej partii.
