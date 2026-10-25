# Starts Nirikshan on http://localhost:8000 (API + built React app in one process).
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
Start-Process "http://localhost:8000"
& .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
