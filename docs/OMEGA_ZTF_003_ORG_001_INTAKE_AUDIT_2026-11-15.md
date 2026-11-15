# OMEGA-ZTF-003 × Silnik Monstrum × ORG-001 — kontrola przyjęcia źródeł

**Data:** 2026-11-15. **Repo docelowe:** `mojealterego/Omega-Studio/main`.
**Materiał źródłowy:** dostarczona w rozmowie specyfikacja 63 plików „OMEGA OMNI × Silnik Monstrum × OMEGA-ORG-001 (MSC2020 Transfinite Edition)”.
**Zakres przyrostu:** bramka integralności fizycznych checkpointów i prawidłowe mieszanie nakładek C². **Nie jest to model ORG, fuzja wag, runtime inferencyjny ani system wydany produkcyjnie.**

## Co było już w repozytorium

Bez duplikowania istniejących implementacji wykorzystujemy:

- `backend/omega_actions/ultimate/safetensors_guard.py`: ograniczony pamięciowo odczyt headera i SHA-256 rzeczywistego pliku; fail-closed dla uszkodzonych tensorów, duplikatów, offsetów.
- `backend/omega_actions/ultimate/pareto_checkpoint.py`: read-only kontrola par LoRA; brak bazy/alpha blokuje merge.
- `backend/omega_actions/ultimate/cinematic_timebase.py`: dokładny zegar A/V na `Fraction`, bez kumulowania błędu zaokrągleń.
- `backend/omega_actions/ultimate/mobile_tile_planner.py`: geometryczny i pamięciowy plan kafelkowania, nie rzeczywisty fotoprocesor 400 MP.
- `backend/omega_actions/dl_adapter.py` oraz `dl_contract.py`: istniejący podpisany kontrakt do Digital-Life; nie należy dublować NARS.

## Nowy zakres implementacji

### `ztf_admission.py`

- Odczyt zgodnego manifestu `omega.unified_model_manifest.v2`; osobna mapa lokalnych nazw plików.
- Rozdzielenie wartości **SHA-256 wpisanej w JSON** i **SHA-256 fizycznych bajtów** obliczonej przez istniejący walidator SafeTensors.
- Ścisły reżim `gradient_steps == 0`, sprawdzanie `ancestry_sha256`, unikalności identyfikatorów, blokada ścieżek `..`, ścieżek absolutnych, symlinków, niebezpiecznych kontenerów i samozadeklarowanych statusów.
- L3/L4 oraz `SUPPORTED` nie mogą przejść bez zewnętrznego dowodu E2E. Obecna warstwa **nigdy** nie nadaje `RELEASED`/`SUPPORTED` i zwraca `NO_INDEPENDENT_E2E_EVIDENCE` nawet przy pełnej integralności.
- Uwaga: ta bramka potwierdza wyłącznie integralność oraz elementarne inwarianty deklaratywne; **nie** potwierdza tożsamości semantycznej wag, zgodności architektury, rzeczywistego treningu, licencji, podpisu benchmarku ani wydajności modelu.

### `c2_blending.py`

- Operator `6t^5 - 15t^4 + 10t^3`, `t ∈ [0, 1]`, wyłącznie dla małych nakładających się pasów pikseli.
- Jego pochodne pierwszego i drugiego rzędu znikają na obu końcach, więc przy przedłużeniu stałym funkcja jest klasy C².
- W dokumencie źródłowym okno Hann / raised cosine nazwano C² — **standardowy Hann o okresie przejścia `cos(πt)` jest C¹, nie C² przy łączeniu ze stałą**.
- Algebraiczna suma wag równa 1 nie gwarantuje braku widocznych szwów po dowolnych filtrach, ani nie dowodzi budżetu RSS na prawdziwym Androidzie.

## Błędy i luki blokujące przejęcie całych 63 plików „jako gotowych”

1. **Proweniencja wag:** rejestr źródłowy deklaruje kilkanaście 64-znakowych ciągów SHA-256 bez fizycznych plików źródłowych. `SRC-016` niepoprawnie traktuje 40-znakowy Git SHA jako SHA-256 pliku przez dopisanie zer. Brak dowodu rozliczenia `17/913` na oryginalnych tensorach; wyliczenie `902 + 11 = 913` jest arytmetyką, nie inwentaryzacją.
2. **Sprzeczność źródłowa:** `AmateurSlider-KREA2_v1.safetensors` w przesłanym JSON ma `container_size_bytes=7025458`, podczas gdy istniejący zapis migracyjny wskazuje `6696848` B (wymaga ponownego bezpośredniego sprawdzenia oryginalnych bajtów). `OMEGA_OMNI_v6_PARETO_RELAY.safetensors` ma już w `docs/OMEGA_X_ARGON_OMNI_INTEGRATION_2026-11-15.md` źródłowe SHA-256 `1b308e1a386100c7395384219054c2273127964aeec45e4abf4c244ff789ef8d`, inne niż `SRC-001` z propozycji.
3. **Fikcyjne benchy:** `Reference-Frontier-A/B` bez nazw modeli i identyfikatorów rzeczywistych przebiegów; `WITH_DIGITAL_LIFE = 0.846` i statystyczna przewaga nie mają wiarygodnego pochodzenia. `BenchmarkAdvantageEvaluator` przy `n=1` stosuje zerową niepewność oraz nie koryguje wielokrotnych porównań.
4. **Błąd weryfikacji Lean:** `Lean4KernelVerifier.verify_proof_source(simulated_kernel_stdout=...)` daje łatwą drogę wprowadzenia udawanego wyniku jądra Lean z kodem wyjścia 0. `IndependentEpistemicVerifier` dopuszcza `lean_kernel_checked=True` jako parametr sterowany przez wywołującego, bez dowodu uruchomienia jądra. Oba mechanizmy wymagają osobnej, odpornej na fałszerstwo realizacji.
5. **Zero-training ≠ potwierdzona fuzja:** matematyczne rzutowanie delty na prawą podprzestrzeń zerową nie gwarantuje „100% zachowania rozumowania” po przejściu przez cały nieliniowy model. `ParetoRelayAuditor.repair_pareto_relay_on_clone` dobiera skalę względem arbitralnej bazy i **nie odzyskuje brakującego rzeczywistego kontraktu** `base_sha256` / `lora_alpha`.
6. **Przetwarzanie 400 MP:** źródłowy `OutOfCore400MPTiler.process_image_out_of_core` alokuje `np.zeros_like(raw_image)` i dwukrotnie wywołuje `raw_image.tobytes()`; przy 400 MP może wymagać wielu gigabajtów i nie spełnia deklaracji out-of-core. Dodatkowo stosuje core crop, bez użycia opisanego algorytmu blendowania nakładek.
7. **Zegar:** `108000` klatek przy `30000/1001` FPS to **3603,6 s**, czyli 1h + 3,6 s, nie dokładnie godzina. Użycie `Fraction` eliminuje dryf obliczeniowy, ale nie dowodzi synchronizacji fizycznego audio/wideo na urządzeniu.
8. **Produkcja i uprawnienia:** Rust gateway `/v1/chat/completions` zwraca wyłącznie echo metadanych modelu; `/v1/math/proofs/verify` zapisuje zgłoszenie, nie wywołuje rzeczywistego Lean. `crates/*` nie mają załączonych `Cargo.toml`, a oddzielne repo `mojealterego/omega-omni-reasoning-genesis` nie było dostępne w bieżącym przeglądzie. `starts_with("CONSENT-SIG-")` nie stanowi kryptograficznej weryfikacji zgody.
9. **Prywatność:** `DifferentialPrivacyAccountant.sanitize_gaussian` aktualizuje koszt RDP, lecz nie blokuje przekroczenia budżetu przed wypuszczeniem szumu; warstwa ochronna jest niekompletna.
10. **Źródła testowe:** `test_omega_ztf_complete.py` używa macierzy 16×16 i syntetycznych metadanych, a testy ORG miniaturowego modelu 64-d; nie są dowodem E2E Qwen/FLUX/Wan, NAL 10–12, realnych 8K, 400 MP lub modelu L4.

## Reprodukcja przyjęcia fizycznych wag

Umieścić pliki fizycznie w jednym zaufanym katalogu i przekazać mapę operatora:

```json
{
  "base": "base.safetensors",
  "contributor:SRC-005": "reasoning.safetensors",
  "candidate": "candidate.safetensors"
}
```

```bash
PYTHONPATH=backend python3 tools/verify_ztf_intake.py \
  --manifest models/UNIFIED_MODEL_MANIFEST.json \
  --artifacts-root /path/to/trusted/models \
  --artifact-map /path/to/artifact_map.json
```

Exit `0` oznacza wyłącznie zgodność bajtów i podstawową integralność, **nigdy** pozytywną bramkę wydania; `2` blokadę, `1` błędny kontrakt. Brak plików lub podanie wzorcowych hashy z dokumentu musi skutkować blokadą.

## Stan wykonawczy po tym przyroście

| Obszar | Status |
|---|---|
| Kod `ztf_admission` i `c2_blending` | IMPLEMENTED, lokalne testy jednostkowe |
| Testy nowych modułów | 26 PASS, lokalnie na syntetycznych danych; walidator źródłowy SafeTensors zastąpiony wyłącznie podczas tego testu lokalnym odpowiednikiem opartym na `safetensors`; w prawdziwym repo użyje istniejącego kodu |
| Test z oryginalnymi modelami Qwen/FLUX/Wan | NOT_VERIFIED |
| Kompilacja Rust | NOT_RUN |
| Fizyczny Galaxy S24 Ultra i Android APK E2E | NOT_VERIFIED |
| NAL 10–12 | OWNER_REPORTED_IMPLEMENTED / SOURCE_MAPPING_PENDING |
| L3/L4 i autoryzacja wydania | BLOCKED |
| Integracja w GitHub `main` | Do niezależnego potwierdzenia po próbie zapisu |
