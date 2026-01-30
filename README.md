# D365 Field Service MCP Server & REST API

MCP (Model Context Protocol) server and REST API for Microsoft Dynamics 365 Field Service integration with Claude AI and Copilot Studio.

## Features

- **Work Order Management** - Query, create, and update work orders
- **Field Technician Scheduling** - Manage bookable resources and technician availability
- **Service Account Queries** - Access customer and service account information
- **OAuth2 Authentication** - Secure Azure AD authentication with token caching
- **OData API Integration** - Direct integration with D365 Web API
- **Dual Transport Modes**:
  - STDIO mode for Claude Desktop integration
  - REST API mode for Copilot Studio and external integrations

## Architecture

This project provides two deployment options:

1. **MCP Server** (`server.py`) - For Claude Desktop integration via STDIO transport
2. **REST API** (`rest_api.py`) - For Copilot Studio, webhooks, and HTTP integrations

Both servers share the same authentication and D365 client libraries for consistency.

## Installation

### Local Development

```bash
# Install dependencies using uv
uv sync

# Test installation
uv run python -c "from src.mcp_d365fs_server import __version__; print(__version__)"
```

### Docker Deployment

```bash
# Build MCP server image (for Claude Desktop)
docker build -t mcp-d365-server:latest .

# Build REST API image (for Copilot Studio)
docker build -f Dockerfile.rest-api -t d365-fs-api:latest .
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in your D365 credentials:

```env
TENANT_ID=your-tenant-id
CLIENT_ID=your-app-client-id
CLIENT_SECRET=your-client-secret
D365_URL=https://your-org.crm.dynamics.com
D365_SCOPE=https://your-org.crm.dynamics.com/.default
```

## Usage

### MCP Server (Claude Desktop)

```bash
# Run locally
uv run python -m src.mcp_d365fs_server.server

# Or via Docker
docker run -it --env-file .env mcp-d365-server:latest
```

Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "d365-field-service": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--env-file", ".env", "mcp-d365-server:latest"]
    }
  }
}
```

### REST API (Copilot Studio)

```bash
# Run locally
uv run uvicorn src.mcp_d365fs_server.rest_api:app --reload --port 8000

# Or via Docker
docker run -p 8000:8000 --env-file .env d365-fs-api:latest
```

Access API documentation at: `http://localhost:8000/docs`

### Azure Deployment

Deploy REST API to Azure Container Apps:

```powershell
# Deploy to Azure
.\deploy-to-azure-v2.ps1
```

## API Endpoints

- `GET /` - Health check and API info
- `GET /health` - Detailed health status
- `GET /api/work-orders` - List work orders (with optional filters)
- `GET /api/work-orders/{id}` - Get work order details
- `GET /api/technicians` - List field technicians
- `GET /api/accounts` - List service accounts

## MCP Tools

When using the MCP server with Claude Desktop:

- `list_work_orders` - Query work orders with filters
- `get_work_order_details` - Get detailed work order information
- `create_work_order` - Create new work orders
- `list_field_technicians` - Query available technicians
- `list_service_accounts` - Query customer accounts
- `check_overdue_work_orders` - Find overdue work orders
- `generate_overdue_report` - Create Excel reports
- `send_overdue_report` - Email reports with OneDrive integration

## Development

### Project Structure

```
src/mcp_d365fs_server/
├── __init__.py          # Package initialization
├── server.py            # MCP server (STDIO mode)
├── rest_api.py          # REST API server (HTTP mode)
├── auth.py              # OAuth2 authentication
└── d365_client.py       # D365 OData client
```

### Running Tests

```bash
# Run local tests
uv run pytest

# Test MCP server
uv run mcp-inspector

# Test REST API
curl http://localhost:8000/api/work-orders
```

## License

MIT
