# OMEGA AppBuilder — kontrakt implementacji

## Cel

Lokalne projektowanie interfejsów Web i natywnych Android bez zależności od chmury. Implementacje: `builder/omega_builder.py` (CLI, eksport deterministyczny) oraz `android/app/src/main/assets/{builder.js,builder-ui.js}` (interfejs offline).

## Schemat

JSON `schema_version=1`, `name` (1–80), `slug` (regex `[a-z][a-z0-9_-]{0,47}`), `package` (co najmniej 3 segmenty), `platform` (`web|android|both`), `theme` (`obsidian-gold|graphite-silver|midnight-blue`), `pages` (1–16), `components` (do 100/stronę). Typy komponentów: `heading`, `paragraph`, `card`, `button`, `input`, `divider`. Akcje ograniczone do `page:<id>` w obrębie projektu.

## Pipeline

1. Walidacja projektu; odrzucenie nieznanych typów i nieistniejących odwołań.
2. Generacja HTML/CSS/JS z CSP i kodowaniem znaków specjalnych.
3. Generacja natywnej Android Activity w Javie z `TextView`, `EditText`, `Button`, `ScrollView`, `LinearLayout`; teksty użytkownika są w Base64, dekodowane w runtime.
4. ZIP z projektem, kodem i manifestem SHA-256 (generator Python); generator JS używa własnego store-only ZIP, bez bibliotek z CDN.
5. Walidacja ZIP przez `zipfile.testzip` i testy kodu źródłowego.

## Gwarancje

Generator nie publikuje kodu ani nie uruchamia GitHub Actions. Nie włącza połączeń zewnętrznych w generowanym Web. Wygenerowany Android nie potrzebuje Internet permission. Kompilacja APK z wygenerowanego projektu wymaga pełnego Android SDK i Gradle.

## Testy

`PYTHONPATH=.:backend python -m pytest -q builder/tests backend/tests` oraz `node --test tests/test_builder.mjs tests/test_ui.mjs`; kompilacja Java ze stubami: `python -m tools.verify_generated_native`. Test stubowy nie zastępuje prawdziwego Android SDK.
