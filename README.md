# D365 Field Service MCP Server

A production-validated **Model Context Protocol (MCP) server** for Microsoft Dynamics 365 Field Service, built with FastMCP and deployed on Azure Container Apps. Enables Microsoft Copilot Studio agents to query live D365 Field Service operational data through natural language.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-Latest-orange?style=flat)](https://github.com/jlowin/fastmcp)
[![Azure Container Apps](https://img.shields.io/badge/Azure%20Container%20Apps-Deployed-0078D4?style=flat&logo=microsoftazure)](https://azure.microsoft.com/en-us/products/container-apps)
[![Copilot Studio](https://img.shields.io/badge/Copilot%20Studio-Integrated-258FFA?style=flat&logo=microsoft)](https://copilotstudio.microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## Overview

This server bridges Microsoft Copilot Studio agents with live Dynamics 365 Field Service data. It solves a key integration challenge: **Copilot Studio supports two distinct integration patterns** — auto-orchestration via MCP protocol and direct tool invocation via Agent-Topic — which require different endpoints. This implementation provides both through a dual-port architecture with an Nginx reverse proxy.

### Validated Integration

- Copilot Studio agent auto-orchestration via MCP protocol
- Teams channel deployment with natural language field service queries
- Azure Container Apps hosting with OAuth2 Client Credentials authentication

---

## Architecture

```
Copilot Studio Agent
        │
        │ HTTPS (port 8080)
        ▼
┌─────────────────────────────┐
│      Nginx Reverse Proxy    │
│          Port 8080          │
└──────────┬──────────────────┘
           │
     ┌─────┴──────┐
     │            │
     ▼            ▼
┌─────────┐  ┌────────────┐
│ FastMCP │  │ Custom API │
│ Port    │  │ Port 8001  │
│  8000   │  │ (FastAPI)  │
└────┬────┘  └─────┬──────┘
     │             │
     └──────┬──────┘
            │
            ▼
    D365 Authenticator
    (OAuth2 Client Credentials)
            │
            ▼
    Dynamics 365 Field Service
    (OData REST API)
```

### Why Dual-Port?

Copilot Studio exposes two integration patterns that require different endpoint behaviours:

| Pattern | Endpoint | Port | Use Case |
|---|---|---|---|
| Auto-orchestration | `/mcp/*` | 8000 (FastMCP) | Agent decides which tools to call |
| Agent-Topic | `/tools/call` | 8001 (FastAPI) | Explicit tool invocation from Topics |

A single FastMCP server cannot satisfy both patterns simultaneously. The Nginx proxy on port 8080 routes traffic to the correct internal server based on the request path, exposing a single external URL to Copilot Studio.

> **Note:** This dual-port architecture was developed iteratively to resolve tool detection failures in Copilot Studio. If you encounter tools not appearing in your Copilot Studio agent, this pattern is the solution.

---

## MCP Tools

| Tool | Description | Key Parameters |
|---|---|---|
| `get_work_orders` | Retrieve work orders with optional filters | `status`, `max_results`, `service_account_name` |
| `get_work_order_details` | Full details for a specific work order | `work_order_id` |
| `list_field_technicians` | List available field technicians | `max_results` |
| `list_service_accounts` | List service accounts / customers | `max_results` |
| `get_overdue_work_orders` | Work orders past expected completion date | `threshold_days` |

### Overdue Work Order Intelligence

The `get_overdue_work_orders` tool calculates overdue status dynamically — not from a D365 field, but by computing:

```
Expected Completion = Created Date + Estimated Duration
Days Overdue = Today - Expected Completion (if status ≠ Completed/Canceled)
Is Critically Overdue = Days Overdue > 7
```

This enables natural language queries like:
- *"Show me all work orders overdue by more than a week"*
- *"Which work orders are critically late?"*

---

## Prerequisites

- Python 3.11+
- [UV package manager](https://github.com/astral-sh/uv) (recommended) or pip
- Azure subscription with:
  - Azure Container Apps environment
  - Azure Container Registry
  - Azure Key Vault (for production secrets)
- Dynamics 365 Field Service environment
- Microsoft Copilot Studio licence

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/AntonTjiptadi/d365-field-service-mcp-server.git
cd d365-field-service-mcp-server
```

### 2. Create virtual environment

```bash
# Using UV (recommended)
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Or using pip
python -m venv .venv
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
# or
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.template .env
```

Edit `.env` with your D365 credentials:

```env
TENANT_ID=your-azure-tenant-id
CLIENT_ID=your-app-registration-client-id
CLIENT_SECRET=your-client-secret
D365_URL=https://yourorg.crm.dynamics.com
D365_SCOPE=https://yourorg.crm.dynamics.com/.default
TRANSPORT=http
API_PORT=8000
API_PORT_CUSTOM=8001
API_HOST=0.0.0.0
```

### 5. Run locally

```bash
# STDIO mode (for Claude Desktop)
python -m src.mcp_d365fs_server.server

# HTTP mode (for Copilot Studio / browser testing)
TRANSPORT=http python -m src.mcp_d365fs_server.server
```

### 6. Verify the server

```bash
# Health check
curl http://localhost:8001/health

# Test a tool call directly
curl -X POST http://localhost:8001/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "get_work_orders", "arguments": {"max_results": 5}}'
```

---

## Azure App Registration

Create an App Registration in Azure Entra ID with the following API permissions for Dynamics 365:

| API | Permission | Type |
|---|---|---|
| Dynamics CRM | `user_impersonation` | Delegated |

Then in your D365 Field Service environment, create an **Application User** linked to the App Registration client ID and assign the appropriate security role (e.g., Field Service — Dispatcher).

---

## Azure Container Apps Deployment

### 1. Build and push the container image

```bash
# Login to Azure Container Registry
az acr login --name <your-registry-name>

# Build and push
docker build -t <your-registry>.azurecr.io/d365-fs-mcp:latest .
docker push <your-registry>.azurecr.io/d365-fs-mcp:latest
```

### 2. Deploy to Azure Container Apps

```bash
az containerapp create \
  --name d365-fs-mcp-server \
  --resource-group <your-rg> \
  --environment <your-aca-environment> \
  --image <your-registry>.azurecr.io/d365-fs-mcp:latest \
  --target-port 8080 \
  --ingress external \
  --env-vars \
    TENANT_ID=secretref:tenant-id \
    CLIENT_ID=secretref:client-id \
    CLIENT_SECRET=secretref:client-secret \
    D365_URL=secretref:d365-url \
    D365_SCOPE=secretref:d365-scope \
    TRANSPORT=http
```

### 3. Note your external URL

Once deployed, your Container App will have an external URL in the format:
```
https://d365-fs-mcp-server.<unique-id>.<region>.azurecontainerapps.io
```

This is the base URL you will register in Copilot Studio.

---

## Copilot Studio Integration

### Connecting via MCP (Auto-orchestration)

1. Open Copilot Studio → your agent → **Tools** → **Add a tool** → **Model Context Protocol**
2. Enter your MCP endpoint: `https://<your-aca-url>/mcp/`
3. Set authentication to **No authentication** (or configure as appropriate for your tenant)
4. The agent will automatically discover all five tools

> **Troubleshooting:** If tools are not detected, verify the `/mcp/` path includes the trailing slash. The Nginx proxy routes `/mcp/*` to the FastMCP server on port 8000. Without the correct path, requests will not reach FastMCP and tool discovery will fail.

### Connecting via Agent-Topic (Direct invocation)

For Agent-Topic patterns using Power Automate Flow, call the custom API endpoint:

```
POST https://<your-aca-url>/tools/call
Content-Type: application/json

{
  "tool_name": "get_work_orders",
  "arguments": {
    "status": "in progress",
    "max_results": 10
  }
}
```

The custom API normalises parameter names automatically — for example, `customer_name` and `account_name` are both accepted as aliases for `service_account_name`.

---

## Project Structure

```
D365-FIELD-SERVICE-MCP-IMPLEMENT/
├── src/
│   └── mcp_d365fs_server/
│       ├── __init__.py
│       ├── auth.py              # OAuth2 Client Credentials token management
│       ├── d365_client.py       # D365 OData API client
│       ├── rest_api.py          # REST API helpers
│       └── server.py            # MCP tools + dual-port server
├── tests/
├── .env.template                # Environment variable template
├── .gitignore
├── .dockerignore
├── Dockerfile                   # Dual-port container (FastMCP + Custom API + Nginx)
├── Dockerfile.rest-api
├── nginx.conf                   # Nginx routing configuration
├── pyproject.toml
└── README.md
```

---

## Related Resources

- [LinkedIn Article Series: AI Agents for D365 Field Services](https://www.linkedin.com/posts/anton-tjiptadi-18b3aa21_erp-artificialintelligence-enterprisesystems-ugcPost-7434234324314513408-ewO2?utm_source=share&utm_medium=member_desktop&rcm=ACoAAASB4nsBTGc0QnwhygXPnMwUa7kpuPCaiJI) — Full build walkthrough including architecture decisions, Copilot Studio integration, and lessons learned
- [D365 F&O MCP Server](https://github.com/AntonTjiptadi/d365-fo-mcp-server) — The follow-on implementation extending this pattern to Finance & Operations

---

## Contributing

Contributions, issues, and feature requests are welcome. If this repository has been useful to your own D365 + MCP work, please consider giving it a ⭐ — it helps others discover the project.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

*Built by [Anton Tjiptadi](https://github.com/AntonTjiptadi) — D365 F&O Solution Architect specialising in Supply Chain Management, Advanced Warehouse Management, and enterprise AI agent development.*
