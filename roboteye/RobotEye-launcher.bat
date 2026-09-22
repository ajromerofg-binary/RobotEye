@echo off
setlocal enabledelayedexpansion
title RobotEye - Sr.Robot Labs

echo ============================================
echo   RobotEye - Lanzador (Windows / modo dev)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el PATH.
    echo.
    echo Descargalo desde https://www.python.org/downloads/
    echo IMPORTANTE: durante la instalacion, marca la casilla
    echo "Add python.exe to PATH" antes de darle a Install.
    echo.
    pause
    exit /b 1
)

if not exist venv (
    echo Primera vez: creando entorno virtual, un momento...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo Instalando/actualizando dependencias (puede tardar la primera vez)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo instalando dependencias. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo Arrancando RobotEye...
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] RobotEye se cerro con un error -- revisa el mensaje de arriba.
    pause
)

endlocal
