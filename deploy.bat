@echo off
cls

REM --- Configuration ---
set "PYTHON_ENV_DIR=C:\deploy\portable_python_env"
set "OUTPUT_DIR=C:\deploy\dist"
REM --------------------

echo =================================
echo  Starting Asset Manager Build
echo =================================

echo [1/3] Cleaning up old distribution...
if exist "%OUTPUT_DIR%" rd /s /q "%OUTPUT_DIR%"

echo [2/3] Creating new distribution folder...
mkdir "%OUTPUT_DIR%"

echo [3/3] Copying all necessary files...
xcopy /E /I /Q /Y "%PYTHON_ENV_DIR%" "%OUTPUT_DIR%\portable_python_env\"
xcopy /E /I /Q /Y "%~dp0application" "%OUTPUT_DIR%\app\"
xcopy /E /I /Q /Y "%~dp0static" "%OUTPUT_DIR%\static\"
xcopy /E /I /Q /Y "%~dp0migrations" "%OUTPUT_DIR%\migrations\"

REM --- Create launcher ---
(
    echo @echo off
    echo Starting Asset Manager... Please open your web browser to http://localhost:8501
    echo.
    cd /d "%%~dp0app"
    "%%~dp0..\portable_python_env\python.exe" -m streamlit run Home.py --server.port 8501 --server.headless true
) > "%OUTPUT_DIR%\Run_App.bat"

echo.
echo =================================
echo  Build Complete! Check the '%OUTPUT_DIR%' folder.
echo =================================
pause