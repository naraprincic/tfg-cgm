@echo off
rem Inicia el prototipo con doble clic: la primera vez instala todo; despues solo arranca.
title Prototipo CGM - iniciar
cd /d "%~dp0"
echo.
echo  ===  Prototipo: mediciones de CGM y eventos cotidianos  ===
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo  Falta Python 3.14. Instalalo desde python.org y volve a abrir este archivo.
  pause
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo  Falta Node.js. Instalalo desde nodejs.org y volve a abrir este archivo.
  pause
  exit /b 1
)

cd backend
if not exist .venv\Scripts\python.exe (
  echo  [1/4] Primera vez: preparando el backend, tarda unos minutos...
  py -3.14 -m venv .venv
  if errorlevel 1 (
    echo  No se pudo usar Python 3.14. Revisa la instalacion con: py --list
    pause
    exit /b 1
  )
  .venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo  No se pudieron instalar las bibliotecas del backend. Revisa la conexion a internet.
    pause
    exit /b 1
  )
)
if not exist .env (
  copy .env.example .env >nul
  echo  [2/4] Se creo el archivo backend\.env.
  echo        Se va a abrir el Bloc de notas: reemplaza TU_CLAVE_DE_POSTGRES por la contrasena
  echo        de PostgreSQL, guarda el archivo y cerralo para seguir.
  notepad .env
)
echo  [3/4] Iniciando el backend...
start "Backend - no cerrar" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app"

cd ..\frontend
if not exist node_modules (
  echo        Primera vez: instalando el frontend, tarda unos minutos...
  call npm install --no-fund --no-audit
  if errorlevel 1 (
    echo  No se pudieron instalar las dependencias del frontend.
    pause
    exit /b 1
  )
)
echo  [4/4] Iniciando el frontend...
start "Frontend - no cerrar" cmd /k "npm run dev"

echo.
echo  Esperando que todo arranque...
timeout /t 15 /nobreak >nul
start "" http://localhost:3000
echo.
echo  Listo: la aplicacion se abrio en el navegador (http://localhost:3000).
echo  Para cargar la cuenta de prueba con datos, usa cargar_demo.bat.
echo  Para cerrar la aplicacion, cerra las dos ventanas negras "Backend" y "Frontend".
echo.
pause
