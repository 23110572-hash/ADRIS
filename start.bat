@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "BACKEND_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "FRONTEND_URL=http://localhost:3000"
set "BACKEND_URL=http://127.0.0.1:8000/docs"
set "START_BACKEND=1"
set "START_FRONTEND=1"

if /I "%~1"=="frontend" set "START_BACKEND=0"
if /I "%~1"=="backend" set "START_FRONTEND=0"
if /I "%~1"=="--frontend-only" set "START_BACKEND=0"
if /I "%~1"=="--backend-only" set "START_FRONTEND=0"

if "%START_FRONTEND%"=="1" (
    if not exist "%FRONTEND_DIR%\package.json" (
        echo [ADRIS] Frontend package was not found:
        echo         %FRONTEND_DIR%\package.json
        exit /b 1
    )
    where node >nul 2>&1
    if errorlevel 1 (
        echo [ADRIS] Node.js is not available on PATH. Next.js requires Node.js 22 or later.
        exit /b 1
    )
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [ADRIS] npm is not available on PATH.
        exit /b 1
    )
    if not exist "%FRONTEND_DIR%\node_modules\next\package.json" (
        echo [ADRIS] Existing frontend dependencies were not found.
        echo [ADRIS] This script never downloads packages automatically.
        echo [ADRIS] Install once from "%FRONTEND_DIR%" with: npm ci
        exit /b 1
    )
)

if "%START_BACKEND%"=="1" (
    if not exist "%BACKEND_DIR%\app\main.py" (
        echo [ADRIS] Backend entry point was not found:
        echo         %BACKEND_DIR%\app\main.py
        exit /b 1
    )
    if not exist "%BACKEND_PYTHON%" (
        echo [ADRIS] Existing backend virtual environment was not found.
        echo [ADRIS] This script never creates or installs it automatically.
        echo [ADRIS] Expected: %BACKEND_PYTHON%
        exit /b 1
    )
    if not exist "%BACKEND_DIR%\.venv\Lib\site-packages\fastapi\__init__.py" (
        echo [ADRIS] FastAPI is missing from the existing backend virtual environment.
        echo [ADRIS] Install the pinned backend requirements once; start.bat will not install them.
        exit /b 1
    )
    if not exist "%BACKEND_DIR%\.venv\Lib\site-packages\uvicorn\__init__.py" (
        echo [ADRIS] Uvicorn is missing from the existing backend virtual environment.
        exit /b 1
    )
)

if /I "%~1"=="--check" (
    echo [ADRIS] Startup check passed.
    echo [ADRIS] Node.js:
    node --version
    echo [ADRIS] npm:
    call npm --version
    echo [ADRIS] Python:
    "%BACKEND_PYTHON%" --version
    echo [ADRIS] No packages were installed or downloaded.
    exit /b 0
)

if "%START_BACKEND%"=="1" (
    echo [ADRIS] Opening FastAPI server window at http://127.0.0.1:8000 ...
    start "ADRIS Backend" /D "%BACKEND_DIR%" cmd.exe /k ""%BACKEND_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

if "%START_FRONTEND%"=="1" (
    echo [ADRIS] Opening Next.js React server window at http://localhost:3000 ...
    start "ADRIS Frontend" /D "%FRONTEND_DIR%" cmd.exe /k "npm run dev"
)

echo [ADRIS] Servers run in the two new command windows.
echo [ADRIS] No virtual environment or npm package is being created or installed.

if "%START_FRONTEND%"=="1" (
    echo [ADRIS] Waiting for the React frontend to answer; this can take up to 90 seconds on the E: drive...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(90); do { try { $response=Invoke-WebRequest -UseBasicParsing -Uri '%FRONTEND_URL%' -TimeoutSec 2; if ($response.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
    if errorlevel 1 echo [ADRIS] Frontend was not ready yet. Read the ADRIS Frontend window for the exact error.
) else (
    timeout /t 3 /nobreak >nul
)

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME_EXE (
    if "%START_FRONTEND%"=="1" if "%START_BACKEND%"=="1" start "" "%CHROME_EXE%" "%FRONTEND_URL%" "%BACKEND_URL%"
    if "%START_FRONTEND%"=="1" if "%START_BACKEND%"=="0" start "" "%CHROME_EXE%" "%FRONTEND_URL%"
    if "%START_FRONTEND%"=="0" if "%START_BACKEND%"=="1" start "" "%CHROME_EXE%" "%BACKEND_URL%"
) else (
    echo [ADRIS] Chrome was not found in a standard location. Using the default browser.
    if "%START_FRONTEND%"=="1" start "" "%FRONTEND_URL%"
    if "%START_BACKEND%"=="1" start "" "%BACKEND_URL%"
)

echo [ADRIS] Close the ADRIS Backend and ADRIS Frontend windows to stop the application.
endlocal
