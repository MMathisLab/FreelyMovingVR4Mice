@echo off
REM VR4Mice rig GUI — Windows quick start
REM Full guide: README.md (section "Windows rig setup")
REM 1. copy config\windows_config.json.example config\config.json  (edit paths)
REM 2. python -m pip install PyQt5 numpy "moviepy>=1.0.3"
REM 3. Test: scp user@server:/shared/gui_menu.npy .
REM 4. Double-click this file or run from cmd in gui_transfer\

set "config_path=default"
set "config_name=config.json"
cd /d "%~dp0"
python main.py || py -3 main.py
if errorlevel 1 pause
