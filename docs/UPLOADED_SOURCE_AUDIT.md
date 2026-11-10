# Audyt pięciu archiwów źródłowych dostarczonych przez użytkownika

| Archiwum | SHA-256 | Rozmiar (bajty) | Uwagi |
|---|---|---:|---|
| `vscode-main.zip` | `d5a1dccdbca61d6a8ea731996ea6b65eb48132e99062e0f350cbd90677dde897` | 77288691 | `package.json`: **Code-OSS 1.143.0**, nie 1.85.1; `LICENSE.txt` obecny |
| `vscode-droidscript-code-master.zip` | `21a11ea795545050224d32f463489a0693e8db623aec5e15795049c3275fc444` | 16115970 | `package.json`: `droidscript-code` 0.3.5; brak widocznego pliku licencji na poziomie repozytorium |
| `vscode-droidscript-docs-master.zip` | `50f3b93dce03f5014e003495eb3c469cd82f19121c7c2c09ce321d9a6e182e8d` | 541118 | `package.json`: `droidscript-docs` 0.1.8; brak widocznego pliku licencji na poziomie repozytorium |
| `termux-app-master.zip` | `a025715aa1f7d0076be5b75c61346890330c4fa69e6d5e2e41b36d0c66d81dc6` | 1224861 | Termux, GPL-3.0-only, wymaga zgodnego `TERMUX_APP__PACKAGE_NAME` i zbudowania pakietów pod odpowiedni `$PREFIX` |
| `llama.cpp-master.zip` | `8e80b0b4a334e1bdcdc2a3edd5e045db3a35b9729d9c3934fd57b21956d15999` | 39116849 | MIT, kod źródłowy, nie skompilowane binaria Android |

Archiwa są zachowane bez modyfikacji w prywatnym pakiecie ZIP jako **materiał referencyjny**, nie jako dowód zintegrowanego runtime. Archiwów DroidScript bez potwierdzonych warunków licencyjnych nie wolno automatycznie publikować w publicznym repozytorium. Kompilacja `vscode-main.zip` nie zapewni parytetu z wersją 1.85.1. Przypięcie commitów źródeł oficjalnych opisano w `config/upstream_sources.lock.json`.
