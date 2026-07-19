@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "BACKEND_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "BROWSER_LAUNCHER=%ROOT%scripts\open-when-ready.ps1"
set "FRONTEND_URL=http://127.0.0.1:3000"
set "BACKEND_URL=http://127.0.0.1:8000/docs"
set "START_BACKEND=1"
set "START_FRONTEND=1"
set "LAUNCH_FRONTEND=1"
set "CHECK_ONLY=0"

if /I "%~1"=="frontend" set "START_BACKEND=0"
if /I "%~1"=="backend" set "START_FRONTEND=0"
if /I "%~1"=="--frontend-only" set "START_BACKEND=0"
if /I "%~1"=="--backend-only" set "START_FRONTEND=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if not "%~1"=="" if /I not "%~1"=="frontend" if /I not "%~1"=="backend" if /I not "%~1"=="--frontend-only" if /I not "%~1"=="--backend-only" if /I not "%~1"=="--check" (
    echo [ADRIS] Unknown option: %~1
    echo [ADRIS] Usage: start.bat [frontend^|backend^|--check]
    exit /b 1
)

if "%START_FRONTEND%"=="1" (
    if not exist "%FRONTEND_DIR%\package.json" (
        echo [ADRIS] Frontend package was not found: "%FRONTEND_DIR%\package.json"
        exit /b 1
    )
    if not exist "%BROWSER_LAUNCHER%" (
        echo [ADRIS] Browser readiness helper was not found: "%BROWSER_LAUNCHER%"
        exit /b 1
    )
    where node >nul 2>&1
    if errorlevel 1 (
        echo [ADRIS] Node.js is not available on PATH. The React/Next.js frontend requires Node.js 22 or later.
        exit /b 1
    )
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [ADRIS] npm is not available on PATH.
        exit /b 1
    )
    for /f "tokens=1 delims=." %%V in ('node -p "process.versions.node"') do set "NODE_MAJOR=%%V"
    if not defined NODE_MAJOR (
        echo [ADRIS] Could not determine the installed Node.js version.
        exit /b 1
    )
    if !NODE_MAJOR! LSS 22 (
        echo [ADRIS] Node.js 22 or later is required. Installed version:
        node --version
        exit /b 1
    )
    if not exist "%FRONTEND_DIR%\node_modules\next\package.json" (
        echo [ADRIS] Existing frontend dependencies were not found.
        echo [ADRIS] start.bat never downloads packages. Install once with: npm ci
        exit /b 1
    )
)

if "%START_BACKEND%"=="1" (
    if not exist "%BACKEND_DIR%\app\main.py" (
        echo [ADRIS] Backend entry point was not found: "%BACKEND_DIR%\app\main.py"
        exit /b 1
    )
    if not exist "%BACKEND_PYTHON%" (
        echo [ADRIS] Existing backend virtual environment was not found: "%BACKEND_PYTHON%"
        echo [ADRIS] start.bat never creates or installs a virtual environment.
        exit /b 1
    )
    if not exist "%BACKEND_DIR%\.venv\Lib\site-packages\fastapi\__init__.py" (
        echo [ADRIS] FastAPI is missing from the existing backend virtual environment.
        exit /b 1
    )
    if not exist "%BACKEND_DIR%\.venv\Lib\site-packages\uvicorn\__init__.py" (
        echo [ADRIS] Uvicorn is missing from the existing backend virtual environment.
        exit /b 1
    )
)

if "%CHECK_ONLY%"=="1" (
    echo [ADRIS] Startup check passed.
    if "%START_FRONTEND%"=="1" (
        echo [ADRIS] Node.js:
        node --version
        echo [ADRIS] npm:
        call npm --version
    )
    if "%START_BACKEND%"=="1" (
        echo [ADRIS] Python:
        "%BACKEND_PYTHON%" --version
    )
    echo [ADRIS] No package or virtual environment was installed.
    exit /b 0
)

if "%START_FRONTEND%"=="1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$connection=Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if(-not $connection){exit 0}; $process=Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $connection.OwningProcess) -ErrorAction SilentlyContinue; $owned=$process.CommandLine -and $process.CommandLine.Contains('%FRONTEND_DIR%'); try{$response=Invoke-WebRequest -UseBasicParsing -Uri '%FRONTEND_URL%' -TimeoutSec 2; $ready=$response.StatusCode -lt 500}catch{$ready=$false}; if($ready -and $owned){Write-Host '[ADRIS] Existing healthy ADRIS frontend will be reused.'; exit 10}; if($owned -and -not $ready){try{Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop; Start-Sleep -Milliseconds 750; Write-Host '[ADRIS] Removed an unresponsive ADRIS frontend process.'; exit 0}catch{Write-Host ('[ADRIS] Port 3000 is held by unresponsive ADRIS process ' + $connection.OwningProcess + '. Close it as Administrator or restart Windows.'); exit 20}}; Write-Host ('[ADRIS] Port 3000 is already used by another process: ' + $connection.OwningProcess); exit 20"
    set "PORT_STATE=!ERRORLEVEL!"
    if "!PORT_STATE!"=="10" set "LAUNCH_FRONTEND=0"
    if "!PORT_STATE!"=="20" exit /b 1
)

if "%START_BACKEND%"=="1" (
    echo [ADRIS] Opening FastAPI server window at http://127.0.0.1:8000 ...
    start "ADRIS Backend" /D "%BACKEND_DIR%" cmd.exe /k ""%BACKEND_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

if "%START_FRONTEND%"=="1" if "%LAUNCH_FRONTEND%"=="1" (
    echo [ADRIS] Opening React/Next.js server window at %FRONTEND_URL% ...
    start "ADRIS Frontend" /D "%FRONTEND_DIR%" cmd.exe /k "npm run dev"
)

if "%START_FRONTEND%"=="1" (
    if "%START_BACKEND%"=="1" (
        start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%BROWSER_LAUNCHER%" -PrimaryUrl "%FRONTEND_URL%" -SecondaryUrl "%BACKEND_URL%"
    ) else (
        start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%BROWSER_LAUNCHER%" -PrimaryUrl "%FRONTEND_URL%"
    )
) else (
    start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%BROWSER_LAUNCHER%" -PrimaryUrl "%BACKEND_URL%"
)

echo [ADRIS] Startup launched. This window can close now.
echo [ADRIS] Chrome will open automatically as soon as the requested service responds.
echo [ADRIS] No dependencies were installed or downloaded.
echo [ADRIS] Close the ADRIS server windows to stop the application.
endlocal
