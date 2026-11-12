[CmdletBinding()]
param([string]$OutputDirectory = (Join-Path $PSScriptRoot '../dist'))
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
$work = Join-Path $root '.build'
New-Item -ItemType Directory -Force -Path $work, $output | Out-Null
python -m PyInstaller --noconfirm --onedir --windowed --name Cove --distpath $output --workpath $work --specpath $work (Join-Path $root 'main.py')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
