Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  PARITY ENGINE: DETERMINISTIC 6-SCENARIO VERIFICATION (699 CHECKS)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

1..6 | ForEach-Object {
    .\parity-engine\.venv\Scripts\python.exe parity-engine\parity_cli.py verify --scenario "scenario_$_"
}

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "  PARITY ENGINE: ARTIFACT-GROUNDED ARCHITECTURE Q&A (META MUSE)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

.\parity-engine\.venv\Scripts\python.exe parity-engine\parity_cli.py ask "How does the engine handle JSESSIONID/Bearer synchronization, MFE popup coexistence, anti-cache timeout prevention, and 4-Eyes Maker/Checker1/Checker2 governance?"
