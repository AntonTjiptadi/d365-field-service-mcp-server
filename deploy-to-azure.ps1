# deploy-to-azure.ps1
# Deploys D365 Field Service REST API to Azure Container Apps

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$EnvironmentName = "d365-fs-env"
)

Write-Host "🚀 Deploying D365 Field Service API to Azure Container Apps" -ForegroundColor Cyan
Write-Host ""

# Step 1: Login to Azure
Write-Host "Step 1: Checking Azure login..." -ForegroundColor Yellow
$loginStatus = az account show 2>$null
if (-not $loginStatus) {
    Write-Host "Not logged in. Opening browser for login..." -ForegroundColor Yellow
    az login
} else {
    Write-Host "✅ Already logged in" -ForegroundColor Green
}

# Step 2: Create Resource Group
Write-Host ""
Write-Host "Step 2: Creating resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location
Write-Host "✅ Resource group created: $ResourceGroup" -ForegroundColor Green

# Step 3: Create Container Apps Environment
Write-Host ""
Write-Host "Step 3: Creating Container Apps environment..." -ForegroundColor Yellow
az containerapp env create `
    --name $EnvironmentName `
    --resource-group $ResourceGroup `
    --location $Location
Write-Host "✅ Environment created: $EnvironmentName" -ForegroundColor Green

# Step 4: Load environment variables from .env
Write-Host ""
Write-Host "Step 4: Loading environment variables..." -ForegroundColor Yellow
$envVars = @()
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            $envVars += "$key=$value"
        }
    }
    Write-Host "✅ Loaded environment variables from .env" -ForegroundColor Green
} else {
    Write-Host "⚠️  No .env file found. You'll need to set environment variables manually." -ForegroundColor Yellow
}

# Step 5: Create Container App (with image from Docker Hub or build from source)
Write-Host ""
Write-Host "Step 5: Deploying container app..." -ForegroundColor Yellow
Write-Host "This will take a few minutes..." -ForegroundColor Gray

# Build image locally first, then deploy
Write-Host "Building Docker image locally..." -ForegroundColor Gray
docker build -f Dockerfile.rest-api -t $AppName`:latest .

# For Azure Container Apps, we'll use the Azure Container Registry or direct deployment
# Option A: Build and deploy in one step (recommended for first deployment)
$deployCmd = "az containerapp up " +
    "--name $AppName " +
    "--resource-group $ResourceGroup " +
    "--environment $EnvironmentName " +
    "--source . " +
    "--dockerfile Dockerfile.rest-api " +
    "--ingress external " +
    "--target-port 8000 " +
    "--query properties.configuration.ingress.fqdn " +
    "-o tsv"

# Add environment variables
foreach ($envVar in $envVars) {
    $deployCmd += " --env-vars `"$envVar`""
}

# Execute deployment
$fqdn = Invoke-Expression $deployCmd

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🌐 Your API is now live at:" -ForegroundColor Cyan
Write-Host "   https://$fqdn" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test your API:" -ForegroundColor Yellow
Write-Host "  curl https://$fqdn/health" -ForegroundColor Gray
Write-Host "  curl https://$fqdn/api/work-orders?limit=3" -ForegroundColor Gray
Write-Host ""
Write-Host "API Documentation:" -ForegroundColor Yellow
Write-Host "  https://$fqdn/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  az containerapp logs show --name $AppName --resource-group $ResourceGroup --follow" -ForegroundColor Gray
Write-Host ""

# Save the URL to a file for easy reference
$fqdn | Out-File -FilePath "azure-api-url.txt" -Encoding UTF8
Write-Host "✅ API URL saved to: azure-api-url.txt" -ForegroundColor Green
