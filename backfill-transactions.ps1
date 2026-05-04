[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$UserId,
    
    [switch]$ResetCursor
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Backfilling Transactions ===" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "requirements.txt")) {
    Write-Host "Error: Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

# Build the command
$command = "python scripts/backfill_transactions.py --user-id $UserId"
if ($ResetCursor) {
    $command += " --reset-cursor"
    Write-Host "Note: This will reset the cursor and fetch ALL historical transactions" -ForegroundColor Yellow
    Write-Host ""
}

# Run the backfill
Invoke-Expression $command

Write-Host ""
