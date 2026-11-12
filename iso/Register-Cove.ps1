$ErrorActionPreference = 'Stop'
$directory = Join-Path $env:SystemRoot 'Cove'
$exe = Join-Path $directory 'Cove.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Cove is missing: $exe" }
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @('CommonPrograms', 'CommonStartup')) {
    $path = Join-Path ([Environment]::GetFolderPath($folder)) 'Cove Desktop.lnk'
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $directory
    $shortcut.Description = 'Open Cove Desktop'
    $shortcut.Save()
}
