# Weryfikacja

Weryfikacja obejmuje Python pytest, Node.js test runner, kompilację czystych klas Java przez javac, kompilację pozostałych klas Java przeciwko **testowym stubom** Android, podpis i integralność APK v2 oraz test interfejsu w Chromium z wstrzykniętymi zasobami HTML/CSS/JS.

Nie wykonano pełnej kompilacji Gradle/Android SDK/NDK, instalacji na fizycznym urządzeniu, testów prawdziwego Termux bootstrap ani uruchomienia GGUF przez llama.cpp na Androidzie. Testowanie interfejsu przez `http://127.0.0.1` i `file://` w Chromium zostało zablokowane przez politykę przeglądarki, więc wykonano test przez `page.set_content` i załadowanie zasobów bez nawigacji. Ten test nie dowodzi działania WebView Android.

Szczegółowe rzeczywiste wyniki znajdują się w `validation/`. Nie należy traktować testów symulacyjnych jako zewnętrznej certyfikacji ani statusu 100% produkcyjnego.
