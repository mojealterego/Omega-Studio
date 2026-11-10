# Lokalny CI/CD i Digital-Life

W katalogu `backend/` znajduje się silnik OMEGA Actions Local. Przygotowanie środowiska:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
omega-actions validate /sciezka/Digital-Life/.github/workflows/python-ci.yml --repo /sciezka/Digital-Life
```

Uruchomienie testów lokalnych wymaga jawnego zezwolenia na wykonanie nieznanego kodu:

```bash
OMEGA_ACTIONS_HOME="$HOME/.omega-actions" omega-actions run \
  /sciezka/Digital-Life/.github/workflows/python-ci.yml \
  --repo /sciezka/Digital-Life --unsafe-native
```

`--unsafe-native` uruchamia komendy z workflowów z uprawnieniami użytkownika lokalnego. Używaj tylko dla repozytoriów, którym ufasz. Tryb kontenerowy wymaga lokalnego Dockera, który nie jest dostarczany w paczce i nie działa w standardowym Androidzie.

Monitorowanie commitów bez GitHub-hosted Actions:

```bash
omega-actions watch /sciezka/Digital-Life/.github/workflows/python-ci.yml \
  --repo /sciezka/Digital-Life --interval 30 --unsafe-native
```

Złożone workflowy mogą korzystać z usług Docker, kontenerów i zewnętrznych akcji, które nie są emulowane przez lokalny silnik. Brak pełnej zgodności nie jest błędem GitHub, lecz ograniczeniem implementacji lokalnej. Dla Digital-Life nie uruchamiano rzeczywistych testów na urządzeniu Android i nie wykonywano żadnych zmian w repozytorium.
