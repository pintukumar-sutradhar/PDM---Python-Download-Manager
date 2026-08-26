@echo off
setlocal
cd /d "%~dp0"
title PDM setup

echo ==^> PDM setup

rem 1. Python 3.10+
set PY=python
where %PY% >nul 2>nul || set PY=py
where %PY% >nul 2>nul || (
    echo ERROR: Python not found. Install from https://www.python.org/downloads/ ^(tick "Add to PATH"^)
    pause
    exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" || (
    echo ERROR: Python 3.10+ required.
    pause
    exit /b 1
)

rem 2. venv
if not exist ".venv\Scripts\python.exe" (
    echo ==^> Creating virtual environment (.venv)
    %PY% -m venv .venv || (echo ERROR: venv failed & pause & exit /b 1)
)
set VPY=.venv\Scripts\python.exe

rem 3. Dependencies
echo ==^> Installing dependencies
"%VPY%" -m pip install --quiet --upgrade pip >nul 2>&1
"%VPY%" -m pip install --quiet -r requirements.txt

rem 4. PySide6
"%VPY%" -c "import PySide6" >nul 2>nul || "%VPY%" -m pip install --quiet PySide6-Essentials

rem 5. N_m3u8DL-RE (optional OTT/HLS engine, win-x64)
set NRE_DIR=%LOCALAPPDATA%\PDM\bin
set NRE=%NRE_DIR%\N_m3u8DL-RE.exe
if not exist "%NRE%" (
    echo ==^> Fetching N_m3u8DL-RE (OTT/HLS engine)
    powershell -NoProfile -Command ^
      "$ProgressPreference='SilentlyContinue'; try { $r = Invoke-RestMethod 'https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest'; $u = ($r.assets | Where-Object { $_.name -match 'win-x64.*\.zip' } | Select-Object -First 1).browser_download_url; New-Item -ItemType Directory -Force '%NRE_DIR%' | Out-Null; Invoke-WebRequest $u -OutFile \"$env:TEMP\nre.zip\"; Expand-Archive -Force \"$env:TEMP\nre.zip\" '%NRE_DIR%'; $exe = Get-ChildItem '%NRE_DIR%' -Recurse -Filter 'N_m3u8DL-RE*.exe' | Select-Object -First 1; if ($exe) { Move-Item $exe.FullName '%NRE%' -Force }; Remove-Item \"$env:TEMP\nre.zip\" -EA SilentlyContinue; Write-Host '    installed' } catch { Write-Host '    WARN: fetch failed (built-in HLS engine will be used)' }"
) else (
    echo ==^> N_m3u8DL-RE already present
)
set PATH=%NRE_DIR%;%PATH%

rem 6. JS runtime hint (optional for YouTube)
where node >nul 2>nul || where deno >nul 2>nul || echo     NOTE: no node/deno found - YouTube usually still works. Install Node.js for max compatibility.

rem 7. Self-test passthrough
if "%~1"=="--live" (
    echo ==^> Running self-test
    set QT_QPA_PLATFORM=offscreen
    "%VPY%" scripts/selftest.py --live
)

rem 8. Launch
echo ==^> Launching PDM
"%VPY%" pdm.py %*
if errorlevel 1 pause
endlocal
