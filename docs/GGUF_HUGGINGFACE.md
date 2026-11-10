# Modele GGUF i Hugging Face

## Implementacja

- Parsery GGUF v2/v3 w Pythonie, Java i JavaScript odczytują nagłówek, liczbę tensorów i metadane, stosując limity rozmiarów i długości tablic. Nie czytają wag modelu.
- `HFDownload` w Pythonie pobiera przez HTTPS, sprawdza przekierowania, obsługuje `Range` resume, limit rozmiaru i opcjonalny SHA-256. Testy HTTP są deterministyczne (MockTransport); nie pobierano dużych modeli przez sieć w tej sesji.
- Źródłowy `NativeBridge.downloadHf` używa `HttpURLConnection`, przechowuje częściowe pliki `.part` i nie przesyła tokenu na niezatwierdzone hosty.
- Wybór modelu na Androidzie w natywnym projekcie korzysta z SAF i kopiuje plik do prywatnego katalogu aplikacji. To **import**, a nie zero-copy mount; wymaga wolnego miejsca.

## Parametry

`context`, `threads`, `batch`, `gpu_layers`, `temperature`, `top_k`, `top_p`, `min_p`, `repeat_penalty`, `seed`, `max_tokens`. Walidowane w Pythonie i JavaScript.

## Inference

`LlamaCli` w backendzie wywołuje zainstalowany lokalnie `llama-cli` przez `subprocess` bez `shell=True`. Nie dołączono binariów llama.cpp ani modeli GGUF. Przy 12 GB RAM wielkość modelu, kwantyzacja i kontekst muszą być dobrane do dostępnej pamięci; nie ma gwarancji działania dużych modeli.

## Przykłady

```bash
omega-models inspect ~/models/model.Q4_K_M.gguf
omega-models download org/model model.Q4_K_M.gguf --revision main --sha256 <oczekiwany_digest_sha256>
omega-models run ~/models/model.Q4_K_M.gguf "Cześć" --llama-cli ~/bin/llama-cli --context 4096 --threads 4
```

Klucz `HF_TOKEN` podaje się w środowisku procesu lub w zaszyfrowanym skarbcu backendu. Token nie jest dodawany do URL. Zasady dostępu do repozytorium i licencja modelu obowiązują niezależnie od aplikacji.

Źródło techniczne: https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md
