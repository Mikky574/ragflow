@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-bge-m3.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Setup failed. See the error above.
if not defined BGE_NO_PAUSE pause
exit /b %RESULT%
