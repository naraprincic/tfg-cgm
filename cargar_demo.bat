@echo off
rem Crea (o vuelve a crear) la cuenta de prueba demo@prototipo.com con datos sinteticos.
title Prototipo CGM - cuenta de prueba
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
  echo  Primero abri iniciar.bat una vez para instalar el programa.
  pause
  exit /b 1
)
echo  Cargando la cuenta de prueba, puede tardar un minuto...
.venv\Scripts\python.exe -m app.cargar_demo
echo.
echo  Usuario: demo@prototipo.com   Contrasena: Glucosa2026
pause
