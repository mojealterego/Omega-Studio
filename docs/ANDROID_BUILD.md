# Kompilacja projektu Android Studio

Katalog `android/` jest projektem Gradle (Android Gradle Plugin 8.6.1, JDK 17, compileSdk 35). Zawiera pełne źródła natywnego `MainActivity`, `NativeBridge`, `SecureVault`, `TermuxBootstrapInstaller` oraz narzędzi GGUF/HF. **Nie był kompilowany przez Android SDK w tej sesji**, ponieważ środowisko nie zawiera SDK/NDK ani zewnętrznego dostępu do repozytoriów Maven.

W środowisku z Android SDK:

```bash
cd android
gradle :app:assembleDebug
```

Wynik Gradle powinien zostać oceniony oddzielnie: `app/build/outputs/apk/debug/app-debug.apk`. Bez zgodnego archiwum bootstrap nadal nie będzie w nim Pythona ani Git.

APK `dist/OMEGA_STUDIO_ANDROID_OFFLINE_PREVIEW_v4.0.0.apk` został zbudowany inną, minimalną ścieżką SDK-independent (ręcznie wygenerowany DEX i AXML) i **nie zawiera klas `SecureVault`, `TermuxBootstrapInstaller` ani `NativeBridge` z projektu Android Studio**. Ma tylko dwa typy DEX: `MainActivity` i uproszczony `NativeBridge.run`.

Wersje APK mogą być podpisane różnymi kluczami. Nie należy nadpisywać wcześniejszej instalacji bez zabezpieczenia danych. Żaden z tych pakietów nie był instalowany na fizycznym urządzeniu w ramach tej sesji.
