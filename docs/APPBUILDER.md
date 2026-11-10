# OMEGA AppBuilder — Code / NoCode

AppBuilder działa lokalnie i generuje dwa rodzaje projektów:

- **Web**: HTML, CSS i JavaScript z Content-Security-Policy, bez zewnętrznych zależności.
- **Android native**: projekt Gradle i Java Activity z natywnymi widżetami TextView, EditText, Button, LinearLayout i ScrollView (bez WebView w wygenerowanej aplikacji).

## Model danych

Projekt JSON ma pola `schema_version=1`, `name`, `slug`, `package`, `platform` (`web|android|both`), `theme` i `pages`. Komponenty: `heading`, `paragraph`, `card`, `button`, `input`, `divider`. Nawigacja ograniczona do `page:<id>`.

## Ochrona danych

- Walidacja nazw, identyfikatorów, liczby stron i komponentów.
- HTML escaping, CSP i podgląd w sandbox iframe.
- Teksty użytkownika w kodzie Java przechowywane jako Base64.
- Brak automatycznej publikacji i wywołań płatnych API.

## Weryfikacja lokalna v1.2.0

- 121 testów Python + 4 podtesty: PASS.
- 15 testów JavaScript: PASS.
- Kompilacja wygenerowanego Java przeciwko lokalnym stubom: PASS.
- Weryfikacja podpisu APK podglądowego: PASS.

**APK podglądowy nie zawiera binariów Termux/Python/Git/llama.cpp.** Do pełnego wydania wymagane są zgodny bootstrap ARM64, Android SDK i test na urządzeniu. Dokumentacja nie przedstawia symulacji jako testu fizycznego.
