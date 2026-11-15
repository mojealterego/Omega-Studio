# OMEGA Studio — audyt źródeł, partia 2 (2026-11-15)

Repozytorium docelowe: mojealterego/Omega-Studio, gałąź main. Wykorzystane trzy PDF-y użytkownika: 145 stron.

## Materiały

1. **Optymalizacja Architektury Systemowej Omega-X.PDF** — 18 stron, rzekoma rekonstrukcja adaptera AmateurSlider-KREA2, inverse-tanh, dithering, harmonizacja RMS i rollback. Kluczowe strony 1, 7–10, 12–17.
2. **Architektura Wirtualnego Silnika Obliczeniowego.PDF** — 54 strony, T-MAC, BitNet, MADDNESS, contextual sparsity, PTX/CUDA interposer, SPSC. Kluczowe strony 1–9, 32–49, 52.
3. **Architektura i Kod Zunifikowanego Silnika.PDF** — 73 strony, AetherOmni-Core, RAW 150 Mpx, kafelkowanie, lokalne invalidacje, re-lighting, zarządzanie pamięcią i canvas. Kluczowe strony 8–13, 16–29, 30–35, 59–62.

## Niezależny wynik: dokument KREA2 nie odpowiada oryginalnemu adapterowi

Zbadano lokalny, rzeczywisty plik AmateurSlider-KREA2_v1.safetensors. Nagłówek odczytano bezpośrednio, niezależnie otwarto plik biblioteką safetensors.safe_open, obliczono SHA-256:

- **6 696 848 bajtów**, nie 12 704;
- **34 696 bajtów nagłówka JSON**, nie brak nagłówka;
- **288 nazwanych tensorów**, w tym 192 F32 i 96 BF16, nie 10 sztucznych bloków FP32;
- SHA-256: 424be9cab885fdeac74652b627a1104c8717b6ca0834553044c6cd4eb3dfe0a1.

Rekonstrukcja z CP1252, arbitralny podział 10 bloków i ich nazwanie slider_block.* nie zachowują struktury oryginalnej LoRA. Dithering nie odzyskuje utraconej informacji, norma L2 nie gwarantuje jakości ani kompatybilności. Nie wdrażać modyfikacji wag z tego PDF bez testów bazowego modelu i niezależnego benchmarku.

Istniejący lokalny projekt OMEGA_KREA2_AmateurSlider_v4 ma własny potok optymalizacji zachowujący klucze. W Omega-Studio nie duplikujemy tej implementacji.

## Selekcja architektoniczna

| Źródło | Wykorzystujemy | Odrzucamy / wstrzymujemy |
|---|---|---|
| KREA2 | Odczyt i weryfikację kontenera safetensors, metadane, SHA-256, fail-closed | Odtwarzanie bajtów z tekstu, przypadkowy dithering jako dekwantyzacja, wyrównanie RMS między niepowiązanymi tensorami |
| Wirtualny substrat | Planowanie pamięci, CPU fallback, badania kwantyzacji niskobitowej | Pełną zamienność CUDA/PTX z GPU/NPU bez testów ABI, zgodności i wydajności |
| AetherOmni | Deterministyczne kafelkowanie, halo, ROI, focus priority, dirty-region invalidation, RAM gates | Deklaracje „zero latency”, „Direct-to-Silicon DMA”, 1 Gpx × 60 fps i fizyczne relighting bez pomiarów |

W dokumencie wirtualnego substratu pokazany kod i testy nie stanowią dowodu obsługi arbitralnych jąder PTX. Standardowy SPSC oparty na std::atomic nie oznacza automatycznie DMA z pominięciem systemu operacyjnego. Wydajność na Samsungu S24 Ultra pozostaje niezweryfikowana.

## Pliki wdrożone do main

- backend/omega_actions/ultimate/safetensors_guard.py — read-only walidator: ścisły JSON bez duplikatów, poprawne dtype i shape, zakresy i kompletność payloadu, limity nagłówka, symlinki, opcjonalny strumieniowy SHA-256. Nie zmienia wag.
- backend/omega_actions/ultimate/mobile_tile_planner.py — planner ROI, halo, dirty region, focus, RAM budget i ograniczenie liczby kafelków. Nie dekoduje RAW, nie przydziela VRAM i nie renderuje obrazów.
- tests/ultimate/test_safetensors_guard.py — poprawne i niepoprawne kontenery.
- tests/ultimate/test_mobile_tile_planner.py — pokrycie obrazu, halo, 150 Mpx, przekroczenie budżetu i deterministyczne próby losowe.

## Ograniczenia pamięci

Pełna 150 Mpx ramka 14 204 × 10 652 pikseli, 4 kanały float32 i 3 jednoczesne bufory wymaga 7 262 448 384 bajtów (~6,76 GiB), nie licząc modeli, cache i narzutów. Planer pozwala ograniczyć pamięć pojedynczego kafelka, ale nie rozwiązuje automatycznie problemu dekodowania RAW ani przechowywania pełnego obrazu. Parametry dostępnej pamięci trzeba ustalać z limitu procesu Android/Termux, nie z nominalnych 12 GB urządzenia.

## Weryfikacja i granice dowodu

- Lokalnie Python 3.13, pytest: 40 testów zaliczonych łącznie z poprzednią partią (7 + 33); compileall OK.
- Walidator sprawdzony na rzeczywistym oryginalnym adapterze KREA2 (288 tensorów, zgodne SHA-256), a także na pliku zapisanym przez bibliotekę safetensors.
- Nie wykonano: pełnej regresji repozytorium, testów Android/S24 Ultra, benchmarków CUDA/NPU, dekodowania RAW, integracji UI/ComfyUI, pomiarów 8K, renderingu 3D ani inferencji modelu bazowego KREA2.

Status: **wdrożone biblioteki domenowe i testy lokalne**, nie ukończony silnik fotograficzny i nie potwierdzone działanie produkcyjne.
