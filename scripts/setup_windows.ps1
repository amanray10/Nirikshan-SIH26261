# One-time setup on Windows (PowerShell). Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "`n[1/5] Checking Python and Node" -ForegroundColor Cyan
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
& $py --version
node --version
npm --version

Write-Host "`n[2/5] Creating Python virtual environment and installing backend packages" -ForegroundColor Cyan
if (-not (Test-Path "backend\.venv")) { & $py -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Write-Host "`n[3/5] Installing and building the React frontend" -ForegroundColor Cyan
Push-Location frontend
npm install
npm run build
Pop-Location

Write-Host "`n[4/5] Checking OCR (needed for scanned documents)" -ForegroundColor Cyan
if ((Get-Command tesseract -ErrorAction SilentlyContinue) -or (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
  Write-Host "Tesseract found." -ForegroundColor Green
} else {
  Write-Host "Tesseract not found. Scanned documents will not be read until you install it:" -ForegroundColor Yellow
  Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki  (tick 'Hindi' and 'Marathi' language data), then re-run this script."
}

Write-Host "`n[5/5] Generating synthetic dossiers, loading the database and running all checks (2-5 minutes)" -ForegroundColor Cyan
Push-Location backend
& .venv\Scripts\python.exe scripts\seed.py --regenerate
& .venv\Scripts\python.exe scripts\evaluate.py
& .venv\Scripts\python.exe -m pytest -q
Pop-Location

Write-Host "`nDone. Start the app with:  scripts\run_windows.bat" -ForegroundColor Green
