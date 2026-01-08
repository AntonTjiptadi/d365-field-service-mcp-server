"""
MCP D365 Field Service Server Package

This package provides MCP (Model Context Protocol) server functionality
for Dynamics 365 Field Service integration with Claude AI.

Main modules:
- server: FastMCP server with tool registration
- auth: OAuth2 authentication with Azure AD
- d365_client: D365 OData API client
- models: Pydantic data models for validation
- tools: MCP tool implementations
"""

__version__ = "0.1.0"
__author__ = "Tony"
__email__ = "tonzgolive@gmail.com"

# Package metadata
__all__ = [
    "server",
    "auth",
    "d365_client",
    "models",
    "tools",
]
