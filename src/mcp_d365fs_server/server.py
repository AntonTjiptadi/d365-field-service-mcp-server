"""
MCP Server for Dynamics 365 Field Service - ENCODING-SAFE VERSION

CRITICAL FIX: Complete STDIO unbuffering with UTF-8 encoding for Windows
This fixes MCP Inspector connection issues and Unicode errors.
"""

# ============================================================================
# WINDOWS FIX - MUST BE ABSOLUTELY FIRST! Before ANY imports!
# ============================================================================
import sys
import os

# Set UTF-8 encoding FIRST - before any output
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Force UTF-8 encoding for stdout/stderr on Windows
if sys.platform == "win32":
    import io
    
    # Replace stdout with UTF-8 encoded, unbuffered wrapper
    sys.stdout = io.TextIOWrapper(
        open(sys.stdout.fileno(), 'wb', 0),
        encoding='utf-8',
        write_through=True,
        line_buffering=False,
        newline='\n',
        errors='replace'  # Replace unencodable chars instead of crashing
    )
    
    # Replace stderr with UTF-8 encoded, unbuffered wrapper
    sys.stderr = io.TextIOWrapper(
        open(sys.stderr.fileno(), 'wb', 0),
        encoding='utf-8',
        write_through=True,
        line_buffering=False,
        newline='\n',
        errors='replace'  # Replace unencodable chars instead of crashing
    )

# END WINDOWS FIX
# ============================================================================

from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

# Import our modules
from .auth import D365Authenticator
from .d365_client import D365Client


# ============================================================================
# Load Environment Variables
# ============================================================================
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = [
    "TENANT_ID",
    "CLIENT_ID", 
    "CLIENT_SECRET",
    "D365_URL",
    "D365_SCOPE"
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    print(f"Error: Missing environment variables: {', '.join(missing_vars)}", file=sys.stderr)
    print(f"Please check your .env file.", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Initialize FastMCP Server
# ============================================================================
mcp = FastMCP("D365 Field Service")

# Initialize authenticator (handles OAuth2 tokens)
authenticator = D365Authenticator(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("D365_SCOPE"),
    verbose=False  # Disable verbose output to avoid encoding issues
)

# Initialize D365 client (handles API calls)
d365_client = D365Client(
    base_url=os.getenv("D365_URL"),
    authenticator=authenticator,
    verbose=False  # Disable verbose output to avoid encoding issues
)


# ============================================================================
# Define MCP Tools
# ============================================================================

@mcp.tool()
async def get_work_orders(
    status: Optional[str] = None,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Retrieve work orders from D365 Field Service.
    
    This tool queries the msdyn_workorder entity and returns a list of work orders.
    You can filter by status and limit the number of results.
    
    Args:
        status: Optional work order status to filter by (e.g., "Open", "In Progress", "Completed")
        max_results: Maximum number of work orders to return (default: 10, max: 100)
    
    Returns:
        List of work order dictionaries with minimal guaranteed fields:
        - msdyn_workorderid: Unique ID
        - msdyn_name: Work order name/title
        - createdon: Created date
        - modifiedon: Modified date
    
    Example:
        work_orders = await get_work_orders(status="Open", max_results=5)
    """
    try:
        # Build OData filter
        filters = []
        if status:
            filters.append(f"msdyn_systemstatus eq '{status}'")
        
        # Query D365
        result = await d365_client.query_work_orders(
            filter_query=" and ".join(filters) if filters else None,
            top=min(max_results, 100)  # Cap at 100
        )
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to retrieve work orders. Check your D365 connection and credentials."
        }


@mcp.tool()
async def get_work_order_details(work_order_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific work order.
    
    This tool retrieves full details for a single work order.
    
    Args:
        work_order_id: The GUID of the work order (msdyn_workorderid)
    
    Returns:
        Dictionary with work order details
    
    Example:
        details = await get_work_order_details("abc123-guid-here")
    """
    try:
        result = await d365_client.get_work_order_by_id(work_order_id)
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": f"Failed to retrieve work order {work_order_id}. Verify the ID is correct."
        }


@mcp.tool()
async def list_field_technicians(max_results: int = 10) -> List[Dict[str, Any]]:
    """
    List available field technicians (bookable resources).
    
    This tool queries the bookableresource entity to get a list of
    field technicians who can be assigned to work orders.
    
    Args:
        max_results: Maximum number of technicians to return (default: 10)
    
    Returns:
        List of technician dictionaries with minimal guaranteed fields:
        - bookableresourceid: Unique ID
        - name: Technician name
        - createdon: Created date
        - modifiedon: Modified date
    
    Example:
        technicians = await list_field_technicians(max_results=20)
    """
    try:
        result = await d365_client.query_bookable_resources(top=max_results)
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to retrieve field technicians."
        }


@mcp.tool()
async def list_service_accounts(max_results: int = 10) -> List[Dict[str, Any]]:
    """
    List service accounts (customers) in D365 Field Service.
    
    This tool queries the account entity to get customer information.
    
    Args:
        max_results: Maximum number of accounts to return (default: 10)
    
    Returns:
        List of account dictionaries with minimal guaranteed fields:
        - accountid: Unique ID
        - name: Account/company name
        - createdon: Created date
        - modifiedon: Modified date
    
    Example:
        accounts = await list_service_accounts(max_results=15)
    """
    try:
        result = await d365_client.query_accounts(top=max_results)
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to retrieve service accounts."
        }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for the MCP server.
    
    This function is called when you run: uv run mcp-server
    It starts the FastMCP server and keeps it running until interrupted.
    """
    try:
        # Start the MCP server (blocks until stopped)
        mcp.run()
        
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
