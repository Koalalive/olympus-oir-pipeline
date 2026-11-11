@echo off
REM convert.bat -- convert every .oir in a folder to OME-TIFF.
REM   convert.bat                 -> convert the folder one level up (default)
REM   convert.bat C:\data\dir     -> convert that folder
REM   convert.bat C:\data\dir info -> print metadata only
setlocal
set "HERE=%~dp0"
set "SRC=%~1"
if "%SRC%"=="" set "SRC=%HERE%.."

if /I "%~2"=="info" (
  python "%HERE%convert_oir.py" "%SRC%" --info
) else (
  python "%HERE%convert_oir.py" "%SRC%" --cfg "%HERE%channels.cfg" --compress zlib
)
pause
