@echo off
REM Preflight checks before starting the rig GUI (see README.md → Windows rig setup)
cd /d "%~dp0"
set "config_path=default"
set "config_name=config.json"
python check_rig_setup.py %* || py -3 check_rig_setup.py %*
if errorlevel 1 pause
