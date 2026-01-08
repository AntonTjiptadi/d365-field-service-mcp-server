# 1. Create README.md
@"
# MCP D365 Field Service Server

MCP (Model Context Protocol) server for Dynamics 365 Field Service integration with Claude AI.

## Features

- Work Order management
- Field Technician scheduling  
- Service Account queries
- OAuth2 authentication with Azure AD
- OData API integration

## Installation

\`\`\`bash
uv sync
\`\`\`

## Configuration

Copy \`.env.example\` to \`.env\` and fill in your credentials.

## Usage

\`\`\`bash
mcp-server
\`\`\`

## License

MIT
"@ | Out-File -FilePath "README.md" -Encoding UTF8

# 2. Test import
uv run python -c "from src.mcp_d365fs_server import __version__; print(__version__)"

# 3. Commit
git add README.md
git commit -m "Add README.md"