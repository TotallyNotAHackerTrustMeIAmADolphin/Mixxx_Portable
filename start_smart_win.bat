@echo off
setlocal
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "DATA_DIR=%BASE_DIR%\Mixxx_Data"
set "SCRIPT_DIR=%BASE_DIR%\Scripts"
set "MIXXX_EXE=C:\Program Files\Mixxx\mixxx.exe"
set "PORTABLE_PYTHON=%SCRIPT_DIR%\python_win\python.exe"

:: 1. Prepare Environment (LOAD mode)
"%PORTABLE_PYTHON%" "%SCRIPT_DIR%\mixxx_path_fixer.py" "%DATA_DIR%" "windows" "load"

:: 2. Launch Mixxx
if not exist "%MIXXX_EXE%" (
    echo Error: Mixxx not found at %MIXXX_EXE%
    pause
    exit /b
)
start /wait "" "%MIXXX_EXE%" --settingsPath "%DATA_DIR%"

:: 3. Post-Flight (SAVE mode)
echo Mixxx closed. Saving machine-specific hardware settings...
"%PORTABLE_PYTHON%" "%SCRIPT_DIR%\mixxx_path_fixer.py" "%DATA_DIR%" "windows" "save"
echo Done.