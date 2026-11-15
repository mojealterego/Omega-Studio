# OMEGA-ORG-001 — kryptograficzna bramka dowodowa Ed25519

Data: 2026-11-15. Zakres: **bezpieczna weryfikacja podpisanego raportu niezależnego weryfikatora**, nie wykonywanie Lean 4, modeli ani benchmarków.

## Dlaczego dodano

Dostarczona specyfikacja ORG-001 przekazuje w `digital_life_bridge.py` wartość `lean_kernel_checked=True` bez kryptograficznego pochodzenia, a `Lean4KernelVerifier.verify_proof_source` akceptuje `simulated_kernel_stdout` jako zamiennik rzeczywistego wyjścia kompilatora. Oba zachowania są niedopuszczalne w produkcyjnej bramce dowodu. Również obecność tekstu `HOST_TESTED` w JSON nie potwierdza niezależnego testu.

## Implementacja

`backend/omega_actions/ultimate/signed_evidence_gate.py`:

- Publiczny klucz **Ed25519** i dozwolone rodzaje atestacji przypina operator hosta, poza modelem i podpisywanym dokumentem.
- Podpis obejmuje kanoniczny JSON (`sort_keys=True`, rozdzielacze `(',', ':')`, UTF-8, bez NaN/Inf).
- Payload musi zawierać `kind`, `subject_sha256`, `evidence_sha256`, `run_id`, `issued_at_utc`, `outcome`, `verifier_identity`.
- Weryfikator sprawdza podpis, tożsamość klucza, jego dozwolony zakres, fizyczne bajty dowodu, powiązanie z modelem i okno ważności (domyślnie 24 h, tolerancja wyprzedzenia zegara 60 s).
- Większość deklaracji o statusie może pozostawać w logach, ale nie powoduje automatycznej promocji. Pozytywny wynik tej bramki to wyłącznie `AUTHENTIC_ATTESTATION_ONLY` z `release_authorized=False`, `kernel_proof_verified=False`.
- Bramka nie przechowuje kluczy prywatnych i nie uruchamia arbitralnego kodu źródłowego Lean/kompilatora na hoście.

## Zakres zaufania i ograniczenia

Poprawna sygnatura pozwala potwierdzić, że nadawca posiadał klucz prywatny i podpisał dane, **nie** że rzeczywiście wykonał `lake env lean`, że jego środowisko było odizolowane albo że przebieg E2E był niezależny. Dla końcowej bramki L3/L4 potrzebne są dodatkowo:

1. Wiarygodny i monitorowany worker w izolowanej piaskownicy, z rzeczywistym kernel-exit-code i logami dowodów.
2. Przypięta wersja `Lean` i `mathlib`, audyt `#print axioms`, odrzucenie `sorryAx`, spójność formalnej sygnatury z tezą nieformalną.
3. Dziennik wydania powiązany z fizycznym SHA-256 modelu, niezależne przebiegi referencyjne, brak samopromocji i jawna akceptacja właściciela.
4. Weryfikacja rotacji i unieważnień kluczy oraz mechanizm anty-replay dla pojedynczego identyfikatora zadania w nadrzędnym, trwałym ledgerze.

## Testy

```bash
PYTHONPATH=backend:. python3 -m pytest -q backend/tests/test_signed_evidence_gate.py
```

Weryfikacja lokalna: **12/12 PASS** dla poprawnego podpisu i przypadków odmownych (fałszywy klucz, zmiana payload, inny model, niezgodne bajty, wygaśnięcie, przesunięcie zegara, nieautoryzowany zakres, nienormatywny status). Łącznie z wcześniejszym przyrostem **38/38 PASS** na hoście. Testy używają generowanego klucza testowego i syntetycznego logu. **NIE** wykonują Lean 4 ani realnego modelu.
