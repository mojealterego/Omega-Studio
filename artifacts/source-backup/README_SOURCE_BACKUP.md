# OMEGA Studio v2.0.0 — kopia źródeł ZIP

Archiwum źródłowe zostało podzielone na części po 512 KiB ze względu na limit transferu repozytoryjnego. Zawiera 341 plików projektu, testy, dokumentację i podpisany APK podglądowy. Nie zawiera pięciu archiwów źródłowych użytkownika, które mają odrębne warunki licencyjne.

Odtworzenie (Linux, macOS, Termux):

```bash
cat OMEGA_Studio_Ultimate_SOURCE_BACKUP_v2.0.0.zip.part* > OMEGA_Studio_Ultimate_SOURCE_BACKUP_v2.0.0.zip
sha256sum OMEGA_Studio_Ultimate_SOURCE_BACKUP_v2.0.0.zip
```

Oczekiwany SHA-256: `ad68eb911dc414511b91737a53af6bd8ad6a089df0de9e77c71cf12d4ffeab60`.

Ta kopia jest źródłowa. Pełny pakiet użytkownika z pięcioma oryginalnymi archiwami jest udostępniany osobno w czacie; nie jest publikowany w publicznym repozytorium. APK w archiwum jest podglądem, nie pełną dystrybucją Termux.
