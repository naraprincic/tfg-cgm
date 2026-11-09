@echo off
rem Carga la cuenta de prueba en la base de datos de la demo en linea (Neon).
title Prototipo CGM - cuenta de prueba en la nube
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
  echo  Primero abri iniciar.bat una vez para instalar el programa.
  pause
  exit /b 1
)
echo  Pega la direccion de conexion de Neon (empieza con postgresql://) y apreta Enter.
echo  Clic derecho pega el texto en esta ventana. No se guarda en ningun archivo.
set /p DATABASE_URL=Direccion: 
if "%DATABASE_URL%"=="" (
  echo  No se ingreso ninguna direccion.
  pause
  exit /b 1
)
set COOKIE_SEGURA=true
echo  Cargando la cuenta de prueba, puede tardar uno o dos minutos...
.venv\Scripts\python.exe -m app.cargar_demo
echo.
pause
