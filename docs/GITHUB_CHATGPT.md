# GitHub i ChatGPT — kontrolowana automatyzacja

## GitHub

Backend Python zawiera `GitHubClient`, `ActionController`, planowanie operacji i mechanizm zatwierdzania. Własny silnik CI nie wywołuje płatnych GitHub-hosted Actions. W aplikacji Java natywny most obsługuje tylko wybrane odczyty API `https://api.github.com`.

Operacje modyfikujące repozytorium wymagają jawnej konfiguracji `OMEGA_GITHUB_WRITE_ENABLED=true`, listy `OMEGA_ALLOWED_REPOS` oraz zatwierdzenia planu. Dostęp do konta GitHub nie oznacza automatycznego prawa do wszystkich repozytoriów.

## ChatGPT / OpenAI

Subskrypcja ChatGPT nie jest tożsama z kluczem OpenAI API. Backend może używać Responses API po wprowadzeniu własnego klucza i włączeniu opcji `OMEGA_ENABLE_PAID_AI=true`; w trybie domyślnym wywołania płatnego AI są wyłączone. Natywny projekt Java zawiera skarbiec na `OPENAI_API_KEY`, ale nie zawiera w APK podglądowym działającej integracji API.

## Uprawnienia i ochrona

- Wymagane jest ograniczenie zakresu tokenów do konkretnych repozytoriów.
- Żaden prompt, model GGUF ani treść pobrana z repozytorium nie może zmienić polityki bezpieczeństwa ani ominąć zatwierdzenia.
- Bezpośrednie `git push`, merge, release, zmiany sekretów i uruchomienie zewnętrznych workflowów nie są domyślnie autoryzowane.
- Nie można zagwarantować „absolutnej automatyzacji” bez uprawnień i ograniczeń; jest to celowo projektowana granica bezpieczeństwa.
