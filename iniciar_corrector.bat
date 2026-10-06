@echo off
chcp 65001 > nul
title Corrector Editorial El Tiempo

if exist "CorrectorEditorial.exe" (
    echo [INFO] Iniciando ejecutable CorrectorEditorial.exe...
    start "" "CorrectorEditorial.exe"
) else if exist "dist\CorrectorEditorial.exe" (
    echo [INFO] Iniciando ejecutable desde carpeta dist...
    start "" "dist\CorrectorEditorial.exe"
) else (
    echo [INFO] Ejecutando con interprete Python...
    python run_monitor.py
)
