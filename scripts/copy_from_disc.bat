@echo off
REM ============================================================
REM  copy_from_disc.bat -- copy an optical disc to a local folder
REM  WITHOUT inheriting Hidden/System/ReadOnly attributes.
REM
REM  Why this exists:
REM    robocopy's DEFAULT /DCOPY is "DA" (Data + Attributes).
REM    DVDs / UDF volumes frequently mark directories Hidden + System
REM    (PowerShell shows them as d-rhs-). Copying attributes makes the
REM    destination folders invisible in Explorer.
REM
REM  Usage:
REM    copy_from_disc.bat E:\Kaspersky D:\data\cd_copy
REM ============================================================
setlocal
if "%~1"=="" (
  echo usage: %~nx0 SRC DST
  echo   SRC = disc path, e.g. E:\Kaspersky
  echo   DST = target folder, e.g. D:\data\cd_copy
  pause
  exit /b 1
)
if "%~2"=="" (
  echo usage: %~nx0 SRC DST
  pause
  exit /b 1
)

set "SRC=%~1"
set "DST=%~2"

REM /DCOPY:D  = copy directory DATA only, never attributes
REM /A-:SH    = clear Hidden + System on anything already present
REM             (harmless when /DCOPY:D is used; repairs a prior bad run)
robocopy "%SRC%" "%DST%" /E /R:3 /W:5 /NP /TEE /DCOPY:D /A-:SH /LOG+:"%DST%\copy.log"
set "RC=%ERRORLEVEL%"

echo.
if %RC% GEQ 8 (
  echo FAILED with exit code %RC%. See "%DST%\copy.log"
) else (
  echo Copied OK ^(robocopy exit code %RC%^; 0-7 means success^).
)
echo.
echo If folders are still hidden, clear attributes recursively:
echo   attrib -h -s -r "%DST%\*" /s /d
pause
exit /b %RC%
