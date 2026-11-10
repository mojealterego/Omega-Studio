$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m omega_actions serve @args
