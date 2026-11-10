# Dostarczone źródła upstream — rejestr v2

Zarchiwizowane źródła dostarczone przez użytkownika pozostają bez zmian w `third_party/source_archives/`. Dokładne SHA-256, rozmiary i liczby wpisów podaje `third_party/UPLOADED_SOURCE_ARCHIVES.json`.

- `vscode-main.zip`: Code-OSS **1.143.0** (`package.json`), MIT. Nie jest to wersja 1.85.1.
- `termux-app-master.zip`: źródła aplikacji Termux, GPL-3.0-only. Nie zawiera gotowego, dopasowanego do `org.omega.actions` bootstrap Termux.
- `llama.cpp-master.zip`: źródła llama.cpp, MIT. Nie zawiera zbudowanego dla Android ARM64 `llama-cli`.
- `vscode-droidscript-code-master.zip`: źródła DroidScript Code 0.3.5; archiwum nie zawiera pliku LICENSE, dlatego licencję oznaczono NOASSERTION i nie integruje się kodu automatycznie.
- `vscode-droidscript-docs-master.zip`: źródła dokumentacji DroidScript 0.1.8; brak pliku LICENSE, analogiczne ograniczenie.

Każdy plik ZIP przeszedł test CRC i kontrolę ścieżek. Umieszczenie źródeł w paczce nie oznacza kompilacji, zgodności ABI ani prawa do redystrybucji na dowolnych warunkach. Przed dystrybucją binarną należy zachować obowiązki odpowiednich licencji, w tym GPL i licencje komponentów zależnych.
