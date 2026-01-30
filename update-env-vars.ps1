# update-env-vars.ps1
# Updates Azure Container App with environment variables from .env file

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "d365-fs-api"
)

Write-Host "🔧 Updating environment variables for Azure Container App..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    exit 1
}

# Read environment variables from .env
Write-Host "Reading .env file..." -ForegroundColor Yellow
$envVarsList = @()

Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    
    # Skip empty lines and comments
    if ($line -and -not $line.StartsWith('#')) {
        if ($line -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            
            # Remove surrounding quotes if present
            $value = $value -replace '^["'']', ''
            $value = $value -replace '["'']$', ''
            
            # Add to list as "KEY=VALUE" format
            $envVarsList += "$key=$value"
            
            Write-Host "  ✓ $key" -ForegroundColor Green
        }
    }
}

if ($envVarsList.Count -eq 0) {
    Write-Host "❌ No environment variables found in .env file!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Found $($envVarsList.Count) environment variables" -ForegroundColor Green
Write-Host ""

# Update container app with environment variables
Write-Host "Updating Container App..." -ForegroundColor Yellow

$updateCmd = "az containerapp update " +
    "--name $AppName " +
    "--resource-group $ResourceGroup " +
    "--output none"

# Add each environment variable
foreach ($envVar in $envVarsList) {
    $updateCmd += " --set-env-vars `"$envVar`""
}

# Execute the update
Invoke-Expression $updateCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Environment variables updated successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The container app will restart automatically..." -ForegroundColor Yellow
    Write-Host "Wait 30-60 seconds, then test your API:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  curl https://d365-fs-api.niceisland-72e89f2d.eastus.azurecontainerapps.io/health" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ Failed to update environment variables" -ForegroundColor Red
    exit 1
}
