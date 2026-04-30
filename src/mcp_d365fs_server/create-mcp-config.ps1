# First, let's check if the file exists
Get-ChildItem *.ps1

# If it doesn't exist, create it directly with this command:
Set-Content -Path "create-mcp-config.ps1" -Value @'
# create-mcp-config.ps1
# Automatically creates MCP Inspector config from .env file

$projectDir = "C:\Projects\MCP_Server\d365-field-service-mcp-implement"
$envFile = "$projectDir\.env"
$mcpDir = "$env:USERPROFILE\.mcp"
$configPath = "$mcpDir\mcp-inspector.json"

Write-Host "🔧 Creating MCP Inspector config..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path $envFile)) {
    Write-Host "❌ Error: .env file not found at $envFile" -ForegroundColor Red
    exit 1
}

# Read .env file
Write-Host "📖 Reading .env file..." -ForegroundColor Yellow
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"')
        $envVars[$key] = $value
    }
}

# Validate required variables
$required = @("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "D365_URL", "D365_SCOPE")
$missing = $required | Where-Object { -not $envVars[$_] }

if ($missing) {
    Write-Host "❌ Error: Missing required environment variables: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

# Create config object
$config = @{
    mcpServers = @{
        "d365-field-service-local" = @{
            command = "uv"
            args = @(
                "--directory",
                $projectDir,
                "run",
                "mcp-d365fs-server"
            )
            env = @{
                TENANT_ID = $envVars["TENANT_ID"]
                CLIENT_ID = $envVars["CLIENT_ID"]
                CLIENT_SECRET = $envVars["CLIENT_SECRET"]
                D365_URL = $envVars["D365_URL"]
                D365_SCOPE = $envVars["D365_SCOPE"]
            }
        }
    }
}

# Create directory if it doesn't exist
Write-Host "📁 Creating config directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $mcpDir | Out-Null

# Write config file
Write-Host "💾 Writing config file..." -ForegroundColor Yellow
$config | ConvertTo-Json -Depth 10 | Set-Content $configPath

Write-Host ""
Write-Host "✅ MCP Inspector config created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Config location: $configPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run: npx @modelcontextprotocol/inspector" -ForegroundColor White
Write-Host "  2. Select 'd365-field-service-local' from the dropdown" -ForegroundColor White
Write-Host "  3. Test your tools!" -ForegroundColor White
Write-Host ""
'@

# Verify it was created
Write-Host "✅ Script file created!" -ForegroundColor Green
Get-ChildItem create-mcp-config.ps1