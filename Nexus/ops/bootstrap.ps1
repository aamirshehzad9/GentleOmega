param([switch]$Up)

Write-Host "[*] Building containers..."
cd $PSScriptRoot
docker compose -f compose.yml build

if ($Up) { docker compose -f compose.yml up -d }