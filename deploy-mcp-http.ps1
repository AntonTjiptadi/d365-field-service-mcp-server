# deploy-mcp-http.ps1
# Deploys MCP server in HTTP mode to Azure Container Apps

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-d365-fs-api",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "d365-mcp-server",
    
    [Parameter(Mandatory=$false)]
    [string]$EnvironmentName = "d365-fs-env",
    
    [Parameter(Mandatory=$false)]
    [string]$RegistryName = "acrd365fsapi"
)

Write-Host "🚀 Deploying MCP Server (HTTP Mode) to Azure Container Apps" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>$null
if (-not $dockerRunning) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker is running" -ForegroundColor Green

# Get ACR login server
Write-Host ""
Write-Host "Getting Azure Container Registry details..." -ForegroundColor Yellow
$acrLoginServer = az acr show --name $RegistryName --resource-group $ResourceGroup --query loginServer -o tsv

if (-not $acrLoginServer) {
    Write-Host "❌ Container Registry not found. Run deploy-to-azure-v2.ps1 first." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Using registry: $acrLoginServer" -ForegroundColor Green

# Build Docker image for MCP server
Write-Host ""
Write-Host "Building MCP server Docker image..." -ForegroundColor Yellow
$imageName = "$acrLoginServer/${AppName}:latest"
docker build -f Dockerfile -t $imageName .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker image built: $imageName" -ForegroundColor Green

# Push to Azure Container Registry
Write-Host ""
Write-Host "Pushing image to Azure Container Registry..." -ForegroundColor Yellow
az acr login --name $RegistryName
docker push $imageName
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Image pushed to ACR" -ForegroundColor Green

# Get ACR credentials
$acrUsername = az acr credential show --name $RegistryName --query username -o tsv
$acrPassword = az acr credential show --name $RegistryName --query "passwords[0].value" -o tsv

# Load environment variables from .env
Write-Host ""
Write-Host "Loading environment variables..." -ForegroundColor Yellow
$envVarsList = @()

Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#')) {
        if ($line -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            $value = $value -replace '^["'']', ''
            $value = $value -replace '["'']$', ''
            $envVarsList += "$key=$value"
        }
    }
}

# Add MCP_TRANSPORT=http for HTTP mode
$envVarsList += "MCP_TRANSPORT=http"
$envVarsList += "API_PORT=8000"
$envVarsList += "API_HOST=0.0.0.0"

Write-Host "✅ Loaded environment variables (HTTP mode enabled)" -ForegroundColor Green

# Deploy Container App
Write-Host ""
Write-Host "Deploying MCP Server..." -ForegroundColor Yellow

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
foreach ($envVar in $envVarsList) {
    $createCmd += " --env-vars `"$envVar`""
}

$fqdn = Invoke-Expression $createCmd

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🌐 MCP Server (HTTP Mode) is now live at:" -ForegroundColor Cyan
Write-Host "   https://$fqdn" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "MCP Endpoint (for Copilot Studio):" -ForegroundColor Yellow
Write-Host "   https://$fqdn/mcp" -ForegroundColor Gray
Write-Host ""
Write-Host "Test MCP Tools Endpoint:" -ForegroundColor Yellow
Write-Host "   https://$fqdn/mcp/list_tools" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  az containerapp logs show --name $AppName --resource-group $ResourceGroup --follow" -ForegroundColor Gray
Write-Host ""

# Save the URL
$fqdn | Out-File -FilePath "azure-mcp-url.txt" -Encoding UTF8
Write-Host "✅ MCP URL saved to: azure-mcp-url.txt" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  NOTE: MCP over HTTP uses Server-Sent Events (SSE) protocol." -ForegroundColor Yellow
Write-Host "    This is different from REST API. Test if Copilot Studio's" -ForegroundColor Yellow
Write-Host "    MCP integration can connect to it." -ForegroundColor Yellow
