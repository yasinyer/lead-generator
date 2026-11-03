@echo off
rem Dubbelklik dit bestand op Windows om de Lead Generator te starten.
setlocal
chcp 65001 >nul
title Lead Generator
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python")
if not defined PY goto nopython

echo.
echo   Eerste keer opstarten: Lead Generator wordt geinstalleerd...
%PY% -m venv .venv
if errorlevel 1 goto fail

:run
".venv\Scripts\python.exe" -m leadgen.bootstrap
if errorlevel 1 goto fail
goto :eof

:nopython
echo.
echo   Python 3.10 of nieuwer is niet gevonden.
echo   1. Installeer Python via de pagina die nu opent.
echo   2. Vink tijdens de installatie "Add python.exe to PATH" aan.
echo   3. Dubbelklik daarna opnieuw op dit bestand.
start "" "https://www.python.org/downloads/"
pause
goto :eof

:fail
echo.
echo   Er ging iets mis. Zie de melding hierboven.
pause
