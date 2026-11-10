# OMEGA Studio — Android / Web / NoCode / Local CI

OMEGA Studio to polskojęzyczny projekt lokalnego środowiska IDE i AppBuildera z interfejsem premium Obsidian & 24K Gold.

## Implementacja v1.2.0

- Wizualny AppBuilder NoCode: strony, komponenty, podgląd, trzy motywy, eksport ZIP.
- Generator aplikacji webowych HTML/CSS/JS oraz źródeł natywnego Androida Java (TextView, Button, EditText).
- Lokalny silnik CI/CD w Pythonie, obsługa GitHub, GGUF, Hugging Face i wielomodelowych dostawców API w pakiecie źródłowym.
- Testy Python, JavaScript i generowanego kodu Java, deterministyczny eksport.
- Digital-Life pozostaje bez zmian; żadne płatne GitHub Actions nie są uruchamiane.

## Ważna informacja

APK z aktualnej paczki jest **podglądem interfejsu**. Nie zawiera jeszcze zgodnych binariów Termux, Python, Git i llama.cpp. Źródła natywnego Androida wymagają Android SDK/Gradle do pełnej kompilacji. Symulacja nie zastępuje testu na fizycznym urządzeniu.

Pełny pakiet źródłowy i APK podglądowy są dostarczane również jako archiwum ZIP w rozmowie ChatGPT.

## Przykład użycia

```bash
python -m builder.omega_builder validate builder/examples/premium-app.json
python -m builder.omega_builder build builder/examples/premium-app.json --output omega-app.zip
```

Repozytorium przeznaczone jest do przechowywania kopii projektu. Żadne workflowy GitHub-hosted Actions nie są wymagane do lokalnych testów.

Licencje komponentów zależnych pozostają zgodne z ich oryginalnymi warunkami.
