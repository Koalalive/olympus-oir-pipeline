@echo off
REM napari_channels.bat -- open a multi-channel OME-TIFF in napari.
REM   Double-click        -> opens the first image in ..\ome\*.ome.tif
REM   Drag a file onto it -> opens that file
setlocal
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
start "" pythonw "%HERE%napari_channels.py" "%IMG%"
exit /b 0
