# Bezpieczeństwo

1. **Sekrety:** źródłowy `SecureVault` używa Android Keystore AES-256-GCM z AAD powiązanym z nazwą sekretu. API nie zwraca wartości tokenu do WebView. APK podglądowy nie zapisuje sekretów.
2. **HTTP:** `HFDownload` dopuszcza wyłącznie HTTPS i ściśle wyliczone hosty HF/CDN. Token HF nie jest przesyłany do hostów CDN. GitHub używa HTTPS z nagłówkiem Authorization.
3. **Workspace:** operacje zapisu plików Java ograniczono do katalogu aplikacji i prostych nazw plików. Backend Python wykonuje workflowy w izolowanych katalogach roboczych; natywny proces nie stanowi pełnej piaskownicy bezpieczeństwa.
4. **GGUF:** limity parserów chronią przed typowymi nadmiernymi alokacjami, ale nie stanowią niezależnego audytu fuzzingowego.
5. **Termux bootstrap:** przed ekstrakcją wymagany SHA-256 i deklaracja prefiksu, staging i kontrola ścieżek. SHA-256 nie stanowi podpisu pochodzenia; bootstrap musi pochodzić z zaufanego procesu budowania.
6. **AI:** działania GitHub write wymagają jawnego zatwierdzenia. Domyślnie brak płatnych operacji AI i GitHub-hosted Actions.
7. **WebView:** natywny projekt Java blokuje ładowanie zewnętrznych stron wewnątrz WebView i kieruje je do przeglądarki systemowej. Podglądowy APK nie ma pełnego `WebViewClient` z projektu Java; nie należy używać go do otwierania niezaufanych URL.

Zewnętrzny audyt kryptograficzny, audyt Android 17 i test penetracyjny nie zostały przeprowadzone. Testy jednostkowe i symulacje nie są równoważne takim audytom.
