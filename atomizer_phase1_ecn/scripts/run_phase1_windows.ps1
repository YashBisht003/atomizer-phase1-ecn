param(
    [int]$MaxFiles = 0,
    [int]$Step = 5,
    [int]$Workers = 6
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[phase1] root: $root"

python .\scripts\extract_ecn_links.py `
  --seed-file .\manifests\seed_pages.txt `
  --out-csv .\manifests\ecn_links.csv

python .\scripts\make_highspeed_manifest.py `
  --in-csv .\manifests\ecn_links.csv `
  --out-csv .\manifests\ecn_highspeed_links.csv

$downloadCmd = @(
  "python", ".\scripts\download_manifest.py",
  "--manifest", ".\manifests\ecn_highspeed_links.csv",
  "--out-dir", ".\data\raw",
  "--workers", "$Workers"
)
if ($MaxFiles -gt 0) {
  $downloadCmd += @("--max-files", "$MaxFiles")
}

& $downloadCmd[0] $downloadCmd[1..($downloadCmd.Length - 1)]

python .\scripts\export_frames.py `
  --input-dir .\data\raw `
  --output-dir .\data\frames `
  --step $Step

Write-Host "[phase1] complete"
