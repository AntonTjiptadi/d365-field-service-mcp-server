# =============================================================================
# Deploy Fixed server.py to Azure
# =============================================================================


# 2. Rebuild
Write-Host "`n2. Building Docker image..." -ForegroundColor Yellow
docker build --no-cache -t acrd365fsapi.azurecr.io/d365-field-service-mcp:latest .
if ($LASTEXITCODE -ne 0) { 
    Write-Host "   ❌ Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Build complete" -ForegroundColor Green

# 3. Push
Write-Host "`n3. Pushing to ACR..." -ForegroundColor Yellow
docker push acrd365fsapi.azurecr.io/d365-field-service-mcp:latest
if ($LASTEXITCODE -ne 0) { 
    Write-Host "   ❌ Push failed!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Pushed" -ForegroundColor Green

# 4. Get digest
Write-Host "`n4. Getting digest..." -ForegroundColor Yellow
$newDigest = az acr repository show --name acrd365fsapi --image d365-field-service-mcp:latest --query "digest" -o tsv
Write-Host "   Digest: $newDigest" -ForegroundColor Cyan

# 5. Deploy
Write-Host "`n5. Deploying to Azure..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

az containerapp update `
  --name d365-mcp-protocol `
  --resource-group rg-d365-fs-api `
  --image "acrd365fsapi.azurecr.io/d365-field-service-mcp@$newDigest" `
  --revision-suffix $timestamp `
  --output none

az containerapp update `
  --name d365-mcp-api `
  --resource-group rg-d365-fs-api `
  --image "acrd365fsapi.azurecr.io/d365-field-service-mcp@$newDigest" `
  --revision-suffix $timestamp `
  --output none

Write-Host "   ✅ Both containers updated" -ForegroundColor Green

# 6. Wait and watch
Write-Host "`n6. Waiting for startup..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host "`n=== LOGS (watch for DEBUG statements!) ===" -ForegroundColor Green
Write-Host "Expected DEBUG output:" -ForegroundColor Cyan
Write-Host "  DEBUG [MODULE]: server.py imported" -ForegroundColor Gray
Write-Host "  DEBUG: __main__ ENTRY POINT" -ForegroundColor Gray
Write-Host "  DEBUG: main() CALLED" -ForegroundColor Gray
Write-Host "  DEBUG: About to call setup_logging()" -ForegroundColor Gray
Write-Host "  DEBUG: setup_logging() CALLED" -ForegroundColor Gray
Write-Host "  DEBUG: stderr reconfigured" -ForegroundColor Gray
Write-Host "  DEBUG: handler created" -ForegroundColor Gray
Write-Host "  DEBUG: logger configured" -ForegroundColor Gray
Write-Host "  [timestamp] - D365-MCP-Server - INFO - ============..." -ForegroundColor Gray
Write-Host "  DEBUG: setup_logging() COMPLETED SUCCESSFULLY" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop watching...`n" -ForegroundColor Yellow

az containerapp logs show --name d365-mcp-protocol --resource-group rg-d365-fs-api --follow
