[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BaseIso,
    [string]$OutputIso = (Join-Path $PSScriptRoot '../dist/Cove-Windows11-x64.iso'),
    [string]$AppDirectory = (Join-Path $PSScriptRoot '../dist/Cove'),
    [switch]$ConsumeRunnerDownload,
    [string]$Oscdimg = ('{0}\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe' -f [Environment]::GetEnvironmentVariable('ProgramFiles(x86)'))
)
$ErrorActionPreference = 'Stop'
$base = (Resolve-Path -LiteralPath $BaseIso).Path
$app = (Resolve-Path -LiteralPath $AppDirectory).Path
$output = [IO.Path]::GetFullPath($OutputIso)
if ($ConsumeRunnerDownload -and (
    $env:GITHUB_ACTIONS -ne 'true' -or !$env:RUNNER_TEMP -or
    $base -ine (Join-Path $env:RUNNER_TEMP 'cove-windows-base.iso')
)) {
    throw 'Only the temporary GitHub Actions download can be consumed.'
}
if ([IO.Path]::GetExtension($base) -ine '.iso' -or [IO.Path]::GetExtension($output) -ine '.iso') {
    throw 'Input and output must be ISO files.'
}
if (Test-Path -LiteralPath $output) { throw "Output already exists: $output" }
if (!(Test-Path -LiteralPath $Oscdimg -PathType Leaf)) { throw 'Install Windows ADK Deployment Tools or supply -Oscdimg.' }
foreach ($file in @('Cove.exe', '_internal\PyQt6\Qt6\bin\QtWebEngineProcess.exe')) {
    if (!(Test-Path -LiteralPath (Join-Path $app $file) -PathType Leaf)) {
        throw "Cove payload is incomplete: $file. Run Build-App.ps1 first."
    }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$stage = Join-Path $tempRoot ('cove-iso-' + [guid]::NewGuid().ToString('N'))
$partial = Join-Path (Split-Path -Parent $output) ('.cove-' + [guid]::NewGuid().ToString('N') + '.iso.partial')
New-Item -ItemType Directory -Path $stage | Out-Null
$mountedHere = $false
try {
    $image = Get-DiskImage -ImagePath $base
    if (!$image.Attached) {
        $image = Mount-DiskImage -ImagePath $base -PassThru
        $mountedHere = $true
    }
    $volumes = @($image | Get-Volume | Where-Object DriveLetter)
    if ($volumes.Count -ne 1) { throw 'Expected one mounted Windows installation volume.' }
    $source = "$($volumes[0].DriveLetter):\"
    foreach ($file in @('setup.exe', 'sources\boot.wim', 'boot\etfsboot.com', 'efi\microsoft\boot\efisys.bin', 'efi\boot\bootx64.efi')) {
        if (!(Test-Path -LiteralPath (Join-Path $source $file) -PathType Leaf)) {
            throw "Expected a stock Windows 11 x64 installation ISO. Missing: $file"
        }
    }
    if (!(Test-Path -LiteralPath (Join-Path $source 'sources\install.wim')) -and
        !(Test-Path -LiteralPath (Join-Path $source 'sources\install.esd'))) {
        throw 'Windows installation image is missing.'
    }
    foreach ($reserved in @('autounattend.xml', 'sources\$OEM$')) {
        if (Test-Path -LiteralPath (Join-Path $source $reserved)) {
            throw "Use unmodified Windows media. Existing customization: $reserved"
        }
    }
    robocopy $source $stage /E /COPY:DT /DCOPY:T /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -ge 8) { throw "Copying Windows media failed: $LASTEXITCODE" }
    if ($ConsumeRunnerDownload) {
        if (!$mountedHere) { throw 'The temporary ISO was already mounted.' }
        Dismount-DiskImage -ImagePath $base
        $mountedHere = $false
        Remove-Item -LiteralPath $base
    }
    $overlay = Join-Path $PSScriptRoot '../iso'
    Copy-Item -LiteralPath (Join-Path $overlay 'autounattend.xml') -Destination $stage
    $payload = Join-Path $stage 'sources\$OEM$\$$\Cove'
    New-Item -ItemType Directory -Force -Path $payload | Out-Null
    robocopy $app $payload /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -ge 8) { throw "Copying Cove failed: $LASTEXITCODE" }
    Copy-Item -LiteralPath (Join-Path $overlay 'Register-Cove.ps1') -Destination $payload
    $bios = Join-Path $stage 'boot\etfsboot.com'
    $uefi = Join-Path $stage 'efi\microsoft\boot\efisys.bin'
    & $Oscdimg '-m' '-o' '-u2' '-udfver102' '-lCOVE_WIN11' "-bootdata:2#p0,e,b$bios#pEF,e,b$uefi" $stage $partial
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $partial -PathType Leaf)) {
        throw "Oscdimg failed: $LASTEXITCODE"
    }
    Move-Item -LiteralPath $partial -Destination $output
    Get-FileHash -Algorithm SHA256 -LiteralPath $output
} finally {
    try {
        if ($mountedHere) { Dismount-DiskImage -ImagePath $base }
    } finally {
        if (Test-Path -LiteralPath $partial -PathType Leaf) { Remove-Item -LiteralPath $partial -Force }
        $resolved = (Resolve-Path -LiteralPath $stage).Path
        if ((Split-Path -Parent $resolved).TrimEnd('\') -eq $tempRoot.TrimEnd('\') -and
            (Split-Path -Leaf $resolved) -match '^cove-iso-[a-f0-9]{32}$') {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
