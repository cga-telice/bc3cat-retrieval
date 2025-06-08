@echo off

REM Start Docker Desktop
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

REM Wait for 5 seconds
timeout /t 5 /nobreak

REM Open a new terminal (Command Prompt)
start cmd.exe /K

REM Change to the specified directory and run the docker-compose command
cd /d D:\users\cesar\dev\phd\price-catalog
docker-compose up --build

