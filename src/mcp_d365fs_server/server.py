"""
MCP Server for Dynamics 365 Field Service

This is the main entry point for the MCP server. It uses FastMCP framework
to expose D365 Field Service operations as MCP tools that Claude can call.

Main responsibilities:
- Initialize FastMCP server
- Load environment configuration
- Register MCP tools (get_work_orders, list_technicians, etc.)
- Handle server lifecycle (startup, shutdown)
- Provide main() entry point for the 'mcp-server' command
"""

import os
import sys
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP
from dotenv import load_dotenv

# Import our modules (we'll create these next)
from .auth import D365Authenticator
from .d365_client import D365Client
# from .models import WorkOrder, Technician, ServiceAccount


# ============================================================================
# STEP 1: Load Environment Variables
# ============================================================================
# Load credentials from .env file
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = [
    "TENANT_ID",
    "CLIENT_ID", 
    "CLIENT_SECRET",
    "D365_URL",
    "D365_SCOPE"
]

for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        print(f"❌ Error: Missing required environment variable: {var}")
        print(f"Please check your .env file and ensure all credentials are set.")
        sys.exit(1)


# ============================================================================
# STEP 2: Initialize FastMCP Server
# ============================================================================
# Create FastMCP server instance
mcp = FastMCP("D365 Field Service")

# Initialize authenticator (handles OAuth2 tokens)
authenticator = D365Authenticator(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("D365_SCOPE")
)

# Initialize D365 client (handles API calls)
d365_client = D365Client(
    base_url=os.getenv("D365_URL"),
    authenticator=authenticator
)


# ============================================================================
# STEP 3: Define MCP Tools
# ============================================================================
# These are the operations Claude can perform on D365 Field Service

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
        List of work order dictionaries with fields:
        - work_order_id: Unique ID
        - work_order_number: Human-readable number
        - name: Work order name/title
        - status: Current status
        - customer_name: Customer name
        - service_account_id: Customer account ID
        - primary_incident_type: Type of service
        - system_status: System status code
        - date_window_start: Scheduled start date
        - date_window_end: Scheduled end date
    
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
    
    This tool retrieves full details for a single work order including
    all fields, related records, and history.
    
    Args:
        work_order_id: The GUID of the work order (msdyn_workorderid)
    
    Returns:
        Dictionary with complete work order details including:
        - All standard fields
        - Customer information
        - Assigned resources
        - Service tasks
        - Products used
        - Actual costs and duration
    
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
        List of technician dictionaries with fields:
        - resource_id: Unique ID
        - name: Technician name
        - resource_type: Type (usually "User")
        - time_zone: Technician's time zone
        - calendar_id: Associated calendar
        - organizational_unit: Business unit
    
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
    Service accounts are the customers who request field service work.
    
    Args:
        max_results: Maximum number of accounts to return (default: 10)
    
    Returns:
        List of account dictionaries with fields:
        - account_id: Unique ID
        - name: Account/company name
        - account_number: Customer account number
        - address: Service address
        - phone: Contact phone
        - email: Contact email
    
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
# STEP 4: Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for the MCP server.
    
    This function is called when you run:
        mcp-server
    
    It starts the FastMCP server and keeps it running until interrupted.
    """
    print("=" * 60)
    print("   MCP Server for Dynamics 365 Field Service")
    print("=" * 60)
    print()
    
    try:
        # Start the MCP server
        # This will block until the server is stopped (Ctrl+C)
        mcp.run()
        
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


# Allow running directly with: python -m mcp_d365fs_server.server
if __name__ == "__main__":
    main()
