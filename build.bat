@echo off
chcp 65001 >nul

echo ================================================
echo   Context Collector Build Script
echo ================================================
echo.

set "VENV_DIR=%CD%\venv"
set "BUILD_DIR=%CD%\build_temp"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

:: Create virtual environment if not exists
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

:: Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

:: Upgrade pip (using python -m pip to avoid errors)
echo Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install customtkinter -q
python -m pip install pyinstaller -q

:: Get customtkinter path
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__).replace('\\', '/'))"') do set CTK_PATH=%%i

echo.
echo CustomTkinter: %CTK_PATH%
echo Building...

:: Clean old builds
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "dist" rmdir /s /q "dist"

:: Build
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "ContextCollector" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --distpath "%CD%\dist" ^
    --workpath "%BUILD_DIR%\build" ^
    --specpath "%BUILD_DIR%" ^
    --clean ^
    --noconfirm ^
    main.py

:: Check result
echo.
if exist "%CD%\dist\ContextCollector.exe" (
    echo ================================================
    echo [SUCCESS] Build completed!
    echo   Output: %CD%\dist\ContextCollector.exe
    for %%A in ("%CD%\dist\ContextCollector.exe") do echo   Size: %%~zA bytes
    echo ================================================
) else (
    echo [ERROR] Build failed
)

:: Deactivate venv
call deactivate

:: Optional: remove temp files
echo.
echo Do you want to remove temp build files? [Y/N]
choice /c yn /n
if errorlevel 2 (
    echo Keeping temp files
) else (
    echo Removing temp files...
    if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
    echo Cleanup complete
)

echo.
pause