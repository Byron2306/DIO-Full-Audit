$ErrorActionPreference = 'Stop'
Write-Host "Using build venv pyinstaller and python"
$venv = 'C:\Users\User\source\repos\Metatron\.venv_build\Scripts'
$pyinstaller = Join-Path $venv 'pyinstaller.exe'
$pip = Join-Path $venv 'pip.exe'
if (-not (Test-Path $pyinstaller)) {
    Write-Host "pyinstaller not found in build venv, installing..."
    & $pip install pyinstaller
}
& $pyinstaller --version
Set-Location -Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) '')
# Ensure we are in unified_agent folder
Set-Location -Path "$PSScriptRoot"
Write-Host "Running pyinstaller..."
& $pyinstaller --onefile --windowed --name MetatronAgent --distpath "dist/windows" --add-data "unified_agent\core;core" --hidden-import tkinter --hidden-import PIL "ui\desktop\main.py"
Write-Host "PyInstaller finished. Check dist/windows for MetatronAgent.exe"
