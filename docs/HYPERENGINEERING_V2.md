# Hyperengineering v2 — rzeczywiste kontrakty

## AST / „Quantum-Topological”

`QuantumASTResonator` buduje wektor w skończeniewymiarowej **klasycznej** zespolonej przestrzeni Hilberta z liczności typów węzłów AST. Porównanie używa kwadratu modułu iloczynu skalarnego, a niezależne reguły sygnalizują `eval`/`exec` i powtórzone nazwy funkcji. Nie ma superpozycji fizycznych kubitów ani automatycznego dowodu bezpieczeństwa. `repair_python_source` wprowadza tylko syntaktycznie sprawdzalny brakujący dwukropek w nagłówku instrukcji Python i zawsze ponownie uruchamia `ast.parse`.

## Holographic Memory Weaver

`HolographicMemoryWeaver` tworzy na dysku indeks SQLite z SHA-256 każdego bloku oraz ograniczoną reprezentacją fazową jego skrótu. `read_verified` sprawdza integralność i zmianę pliku; długość odczytu jest ograniczona do 1 MiB. Duże pliki mogą być przetwarzane okienkowym `mmap` bez ładowania całości do RAM. Narzut I/O pozostaje fizycznie niezerowy.

## Neuromorphic Synapse

`NeuromorphicSynapse` implementuje deterministyczną, klasyczną regułę STDP z wykładniczym oknem czasowym. Maksymalnie 64 agentów, nieujemne wagi, ograniczenie kolejek i monotoniczny zegar. Nie istnieje nieskończona skalowalność na skończonym telefonie.

## Self-Evolving CI/CD

`AdaptiveCI` przygotowuje deterministyczny plan kompilacji składni Pythona. Dopuszcza wyłącznie znany zestaw argumentów, wymaga świadomego zatwierdzenia przez operatora i weryfikuje HMAC planu. Nie wdraża samoczynnie niezweryfikowanego kodu i nie uruchamia skryptów repozytorium w tle.

## Sieć mobilna

`simulate_mobile_network` odtwarza utratę pakietów, jitter i przełączenia Wi-Fi/LTE/5G z deterministycznym ziarnem. Test nie emuluje modemu, stosu radiowego ani rzeczywistego Android WebSocket.

## Android ARM64

`android/native/omega_runtime.c` jest samodzielnym modułem C, zbudowanym przez Clang 17 jako prawdziwy ELF64 `EM_AARCH64`. Eksportuje `omega_runtime_abi`, `omega_is_gguf_header` i `omega_crc32`. `tools/build_native_arm64.py` weryfikuje nagłówek ELF i SHA-256. Jest to natywny moduł diagnostyczny, a nie Termux ani interpreter Python.
