# deploy-to-azure-v2.ps1
# Improved deployment using Azure Container Registry

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$EnvironmentName = "d365-fs-env",
    
    [Parameter(Mandatory=$false)]
    [string]$RegistryName = "acrd365fsapi"
)

Write-Host "🚀 Deploying D365 Field Service API to Azure Container Apps (v2)" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>$null
if (-not $dockerRunning) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker is running" -ForegroundColor Green

# Step 1: Verify Azure login
Write-Host ""
Write-Host "Step 1: Checking Azure login..." -ForegroundColor Yellow
$loginStatus = az account show 2>$null
if (-not $loginStatus) {
    Write-Host "Not logged in. Opening browser for login..." -ForegroundColor Yellow
    az login
}
Write-Host "✅ Logged in to Azure" -ForegroundColor Green

# Step 2: Resource group already exists, skip creation
Write-Host ""
Write-Host "Step 2: Verifying resource group..." -ForegroundColor Yellow
$rgExists = az group show --name $ResourceGroup 2>$null
if (-not $rgExists) {
    Write-Host "Creating resource group..." -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location
}
Write-Host "✅ Resource group ready: $ResourceGroup" -ForegroundColor Green

# Step 3: Environment already exists, skip creation
Write-Host ""
Write-Host "Step 3: Verifying Container Apps environment..." -ForegroundColor Yellow
$envExists = az containerapp env show --name $EnvironmentName --resource-group $ResourceGroup 2>$null
if (-not $envExists) {
    Write-Host "Creating Container Apps environment..." -ForegroundColor Yellow
    az containerapp env create `
        --name $EnvironmentName `
        --resource-group $ResourceGroup `
        --location $Location
}
Write-Host "✅ Environment ready: $EnvironmentName" -ForegroundColor Green

# Step 4: Create Azure Container Registry
Write-Host ""
Write-Host "Step 4: Creating Azure Container Registry..." -ForegroundColor Yellow
$acrExists = az acr show --name $RegistryName --resource-group $ResourceGroup 2>$null
if (-not $acrExists) {
    az acr create `
        --resource-group $ResourceGroup `
        --name $RegistryName `
        --sku Basic `
        --admin-enabled true
    Write-Host "✅ Container Registry created: $RegistryName" -ForegroundColor Green
} else {
    Write-Host "✅ Container Registry already exists: $RegistryName" -ForegroundColor Green
}

# Get ACR login server
$acrLoginServer = az acr show --name $RegistryName --resource-group $ResourceGroup --query loginServer -o tsv

# Step 5: Build Docker image locally
Write-Host ""
Write-Host "Step 5: Building Docker image locally..." -ForegroundColor Yellow
$imageName = "$acrLoginServer/${AppName}:latest"
docker build -f Dockerfile.rest-api -t $imageName .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker image built: $imageName" -ForegroundColor Green

# Step 6: Push to Azure Container Registry
Write-Host ""
Write-Host "Step 6: Pushing image to Azure Container Registry..." -ForegroundColor Yellow
az acr login --name $RegistryName
docker push $imageName
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Image pushed to ACR" -ForegroundColor Green

# Step 7: Get ACR credentials
$acrUsername = az acr credential show --name $RegistryName --query username -o tsv
$acrPassword = az acr credential show --name $RegistryName --query "passwords[0].value" -o tsv

# Step 8: Load environment variables from .env
Write-Host ""
Write-Host "Step 7: Loading environment variables..." -ForegroundColor Yellow
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
    Write-Host "⚠️  No .env file found" -ForegroundColor Yellow
}

# Step 9: Deploy Container App
Write-Host ""
Write-Host "Step 8: Deploying Container App..." -ForegroundColor Yellow
Write-Host "This will take 2-3 minutes..." -ForegroundColor Gray

# Check if app exists
$appExists = az containerapp show --name $AppName --resource-group $ResourceGroup 2>$null

if (-not $appExists) {
    # Create new app
    $createCmd = "az containerapp create " +
        "--name $AppName " +
        "--resource-group $ResourceGroup " +
        "--environment $EnvironmentName " +
        "--image $imageName " +
        "--target-port 8000 " +
        "--ingress external " +
        "--registry-server $acrLoginServer " +
        "--registry-username $acrUsername " +
        "--registry-password `"$acrPassword`" " +
        "--cpu 0.25 --memory 0.5Gi " +
        "--min-replicas 1 --max-replicas 1 " +
        "--query properties.configuration.ingress.fqdn " +
        "-o tsv"
    
    # Add environment variables
    foreach ($envVar in $envVars) {
        $createCmd += " --env-vars `"$envVar`""
    }
    
    $fqdn = Invoke-Expression $createCmd
} else {
    # Update existing app
    $updateCmd = "az containerapp update " +
        "--name $AppName " +
        "--resource-group $ResourceGroup " +
        "--image $imageName " +
        "--query properties.configuration.ingress.fqdn " +
        "-o tsv"
    
    # Add environment variables
    foreach ($envVar in $envVars) {
        $updateCmd += " --set-env-vars `"$envVar`""
    }
    
    $fqdn = Invoke-Expression $updateCmd
}

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

# Save the URL to a file
$fqdn | Out-File -FilePath "azure-api-url.txt" -Encoding UTF8
Write-Host "✅ API URL saved to: azure-api-url.txt" -ForegroundColor Green
