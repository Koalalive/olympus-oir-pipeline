@echo off
REM open_in_fiji.bat -- open an OME-TIFF in Fiji/ImageJ as a composite view.
REM   Double-click        -> opens the first image in ..\ome\*.ome.tif
REM   Drag a file onto it -> opens that file
REM
REM Set FIJI to your Fiji.app folder, or remove the line if ImageJ is on PATH.
setlocal
if not defined FIJI set "FIJI=C:\Program Files\Fiji.app"
set "HERE=%~dp0"
set "IMG=%~1"

if not "%IMG%"=="" goto run
for %%f in ("%HERE%..\ome\*.ome.tif") do (
  set "IMG=%%~ff"
  goto run
)

:run
if "%IMG%"=="" (
  echo No image found in "%HERE%..\ome"
  pause
  exit /b 1
)
echo Opening: %IMG%
start "" "%FIJI%\ImageJ-win64.exe" -macro "%HERE%open_merge.ijm" "%IMG%"
exit /b 0
