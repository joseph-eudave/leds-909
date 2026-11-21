@echo off
setlocal
cd /d "%~dp0"

set PY=py -3.12
set NAME=VJ_GUI
set DIST=..\dist

echo ==========================================
echo  Building %NAME%.exe (VJ GUI launcher)
echo ==========================================

%PY% -m pip install --quiet PySide6 pyinstaller 2>nul

if exist %DIST%\%NAME% rmdir /s /q %DIST%\%NAME%
if exist build\%NAME% rmdir /s /q build\%NAME%

%PY% -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --distpath %DIST% ^
  --name %NAME% ^
  --collect-submodules PySide6.QtWebEngineWidgets ^
  --collect-data PySide6.QtWebEngine ^
  vj_gui.py

if errorlevel 1 (
    echo BUILD FAILED
    pause
    exit /b 1
)

copy vj_gui_settings.txt %DIST%\ 2>nul
echo.
echo Built: %DIST%\%NAME%.exe
echo Copy it anywhere; it remembers the last TD PC ip.
pause
