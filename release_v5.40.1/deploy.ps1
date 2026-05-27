# EasyCord v5.40.1 Local Release Preparation Script

Write-Host "Preparing EasyCord v5.40.1 local release..." -ForegroundColor Cyan

Write-Host "Verifying Python syntax..."
python -m compileall -q easycord tests scripts
if ($LASTEXITCODE -ne 0) {
    Write-Error "Syntax verification failed."
    exit 1
}

Write-Host "Running CI-style Ruff gate..."
python -m ruff check easycord tests --select E9,F63,F7,F82
if ($LASTEXITCODE -ne 0) {
    Write-Error "Ruff verification failed."
    exit 1
}

Write-Host "Running full test suite..."
$env:PYTHONPATH = (Get-Location).Path
pytest tests/ -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Full test suite failed."
    exit 1
}

Write-Host "Running i18n performance benchmark..."
python scripts/benchmark_i18n.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Benchmark failed."
    exit 1
}

Write-Host "Building distribution package..."
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
python -m build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

Write-Host "Checking built artifacts when twine is available..."
python -m twine --version *> $null
if ($LASTEXITCODE -eq 0) {
    python -m twine check dist/*
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Twine artifact validation failed."
        exit 1
    }
} else {
    Write-Host "twine is not installed; skipping artifact validation." -ForegroundColor Yellow
}

Write-Host "`nLocal v5.40.1 release preparation complete. Assets are ready in dist/." -ForegroundColor Green
Write-Host "Expected assets:"
Write-Host " - dist/easycord-5.40.1-py3-none-any.whl"
Write-Host " - dist/easycord-5.40.1.tar.gz"
Write-Host "No tag, push, GitHub release, or PyPI upload was performed by this script."
Write-Host "Review release_v5.40.1/notes.md and dist/ before publishing manually."
