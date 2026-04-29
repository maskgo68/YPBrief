@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "API_PORT=48787"
set "WEB_PORT=45173"
set "LOG_DIR=%ROOT%\logs"
set "API_CMD=%LOG_DIR%\run-api.cmd"
set "WEB_CMD=%LOG_DIR%\run-web.cmd"
set "API_LOG=%LOG_DIR%\api.log"
set "WEB_LOG=%LOG_DIR%\web-ui.log"

title YPBrief Launcher
cd /d "%ROOT%"
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================================
echo  YPBrief one-click launcher
echo ============================================================
echo  Project: %ROOT%
echo  API:     http://127.0.0.1:%API_PORT%
echo  Web UI:  http://127.0.0.1:%WEB_PORT%
echo  Logs:    %LOG_DIR%
echo ============================================================
echo.

echo [1/4] Stopping old processes on ports %API_PORT% and %WEB_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports=@(%API_PORT%,%WEB_PORT%); $conns=Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | Where-Object {$_.State -eq 'Listen'}; $ids=$conns | Select-Object -ExpandProperty OwningProcess -Unique; foreach($id in $ids){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }"

echo.
echo [2/4] Starting API in a visible CMD window...
(
  echo @echo off
  echo title YPBrief API - http://127.0.0.1:%API_PORT%
  echo cd /d "%ROOT%"
  echo set "PYTHONPATH=%ROOT%\src"
  echo echo [YPBrief API] Starting FastAPI backend...
  echo echo [YPBrief API] Log file: "%API_LOG%"
  echo python "%ROOT%\scripts\tee_run.py" "%API_LOG%" -- python -m uvicorn ypbrief_api.app:app --host 127.0.0.1 --port %API_PORT%
  echo echo.
  echo echo [YPBrief API] Process exited. Press any key to close.
  echo pause ^>nul
) > "%API_CMD%"
start "YPBrief API - http://127.0.0.1:%API_PORT%" cmd /k ""%API_CMD%""

echo [3/4] Starting Web UI in a visible CMD window...
(
  echo @echo off
  echo title YPBrief Web UI - http://127.0.0.1:%WEB_PORT%
  echo cd /d "%ROOT%\web"
  echo echo [YPBrief Web UI] Starting Vite frontend...
  echo echo [YPBrief Web UI] Log file: "%WEB_LOG%"
  echo python "%ROOT%\scripts\tee_run.py" "%WEB_LOG%" -- npm run dev -- --host 127.0.0.1 --port %WEB_PORT% --strictPort
  echo echo.
  echo echo [YPBrief Web UI] Process exited. Press any key to close.
  echo pause ^>nul
) > "%WEB_CMD%"
start "YPBrief Web UI - http://127.0.0.1:%WEB_PORT%" cmd /k ""%WEB_CMD%""

echo.
echo [4/4] Waiting for API and Web UI to become ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline=(Get-Date).AddSeconds(60); $okApi=$false; $okWeb=$false; while((Get-Date) -lt $deadline -and (-not ($okApi -and $okWeb))){ try { Invoke-WebRequest 'http://127.0.0.1:%API_PORT%/api/auth/status' -UseBasicParsing -TimeoutSec 2 | Out-Null; $okApi=$true } catch {}; try { Invoke-WebRequest 'http://127.0.0.1:%WEB_PORT%' -UseBasicParsing -TimeoutSec 2 | Out-Null; $okWeb=$true } catch {}; Start-Sleep -Milliseconds 600 }; if($okApi -and $okWeb){ Write-Host '[YPBrief] Ready.'; exit 0 } else { if(-not $okApi){ Write-Host '[YPBrief] API is not ready yet. Check the YPBrief API window.' }; if(-not $okWeb){ Write-Host '[YPBrief] Web UI is not ready yet. Check the YPBrief Web UI window.' }; exit 1 }"

echo.
echo Opening browser...
start "" "http://127.0.0.1:%WEB_PORT%"

echo.
echo ============================================================
echo  Started. Keep the two service windows open:
echo  - YPBrief API      shows backend logs
echo  - YPBrief Web UI   shows frontend/Vite logs
echo.
echo  Log files are also saved to:
echo  - %API_LOG%
echo  - %WEB_LOG%
echo.
echo  To stop the app, close those two windows.
echo ============================================================
echo.
pause
