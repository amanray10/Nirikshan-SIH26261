# Development mode: FastAPI with auto-reload on :8000 and Vite hot reload on :5173.
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
Set-Location "$root\frontend"
Start-Process "http://localhost:5173"
npm run dev
