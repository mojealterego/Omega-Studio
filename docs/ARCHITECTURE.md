# Architektura OMEGA Studio

## Trzy warstwy

1. **APK offline**: WebView ładuje wyłącznie `file:///android_asset/index.html`. DEX podglądowy zawiera tylko `MainActivity` i most do systemowego `/system/bin/sh`. Nie korzysta z localhost. Ustawienia modelu i szkice przechowywane są w localStorage, ale nie są tam przechowywane sekrety.
2. **Natywny projekt Android Studio**: Java Activity z SAF, asynchroniczny `NativeBridge`, `SecureVault` z Android Keystore AES-256-GCM, `TermuxBootstrapInstaller`, pobieranie HF z HTTPS, walidacja GGUF, kontrola dostępu do workspace i GitHub API GET. Kod natywny jest przygotowany do kompilacji SDK, ale testowano go tylko kompilatorem javac z testowymi stubami Android.
3. **Backend Python**: `omega_actions` obsługuje DAG/matrix/steps, lokalne akcje, logi SSE, artefakty, SQLite WAL, model manager, HFDownload, GGUFInspector, LlamaCli, GitHub policy engine i agent gateway. Jest uruchamiany w osobnym procesie, nie w APK podglądowym.

## Granice zaufania

- JavaScript w WebView nie otrzymuje tokenów ani możliwości ich odczytu. Metody natywne służą do zapisu i użycia tokenów bez zwracania wartości do JS.
- GitHub: odczyt z aplikacji Java; w backendzie zapisy wymagają polityki allowlist + jawnego zatwierdzenia.
- HF: pobieranie do katalogu aplikacji z weryfikacją hosta, TLS i limitu rozmiaru. Model nie jest uruchamiany bez jawnego działania użytkownika.
- CI: wykonanie kodu jest z natury uprzywilejowane w ramach użytkownika lokalnego; tryb natywny nie jest kontenerową izolacją bezpieczeństwa.
- Termux: tylko bootstrap skompilowany dla identyfikatora aplikacji. Nie jest bezpieczne kopiowanie gotowego `com.termux` bootstrap do `org.omega.actions`.

## Przepływ danych

```text
Editor / GGUF / CI / GitHub / Secrets (UI)
            | JavaScriptInterface (trusted asset only)
            v
       NativeBridge (Android)
       |      |         |
  Keystore  HTTPS    SAF / files
       |      |         |
     GitHub  HF    workspace/models

Python backend (oddzielny proces):
  REST/CLI -> Compiler -> DAG scheduler -> worker -> artifacts/logs
               |             |
           Vault/Policy    Model manager -> llama-cli (opcjonalny)
```

## Kompatybilność z Digital-Life

Repozytorium jest traktowane tylko jako źródło workflowów. Silnik Python potrafi wczytać `.github/workflows/*.yml`, ale nie deklaruje pełnej kompatybilności z każdą akcją marketplace, usługą Docker ani środowiskiem GPU. Projekt nie modyfikuje Digital-Life i nie uruchamia GitHub Actions.
