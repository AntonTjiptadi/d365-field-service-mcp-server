"""
MCP Server for Dynamics 365 Field Service - DUAL-PORT WITH NGINX PROXY

Architecture:
- FastMCP server (port 8000) - MCP protocol for auto-orchestration
- Custom API server (port 8001) - Direct tool calls for Agent-Topic
- Nginx reverse proxy (port 8080) - Routes external traffic to both servers

External endpoints (via nginx on port 8080):
1. /mcp/* → FastMCP protocol for Copilot Studio auto-orchestration
2. /tools/call → Custom API for Copilot Studio Agent-Topic
3. /health → Health monitoring

This version includes comprehensive logging for debugging and monitoring.
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
    
    sys.stdout = io.TextIOWrapper(
        open(sys.stdout.fileno(), 'wb', 0),
        encoding='utf-8',
        write_through=True,
        line_buffering=False,
        newline='\n',
        errors='replace'
    )
    
    sys.stderr = io.TextIOWrapper(
        open(sys.stderr.fileno(), 'wb', 0),
        encoding='utf-8',
        write_through=True,
        line_buffering=False,
        newline='\n',
        errors='replace'
    )

# END WINDOWS FIX
# ============================================================================

# ============================================================================
# DEBUG: Module is being imported
# ============================================================================
print("="*80, file=sys.stderr, flush=True)
print("DEBUG [MODULE]: server.py imported", file=sys.stderr, flush=True)
print("="*80, file=sys.stderr, flush=True)

import logging
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

# Import our modules
from .auth import D365Authenticator
from .d365_client import D365Client

# For custom API endpoint
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from datetime import datetime, timedelta, timezone

# ============================================================================
# Global logger - will be configured in setup_logging()
# ============================================================================
logger = None


# ============================================================================
# Logging Setup Function - MUST be called from main() BEFORE FastMCP starts!
# ============================================================================
def setup_logging():
    """
    Configure logging for the MCP server.
    CRITICAL: This must be called from main() BEFORE FastMCP starts
    to prevent FastMCP from overriding our logging configuration.
    """
    global logger
    
    print("="*80, file=sys.stderr, flush=True)
    print("DEBUG: setup_logging() CALLED", file=sys.stderr, flush=True)
    print("="*80, file=sys.stderr, flush=True)
    
    try:
        # Configure stderr for unbuffered output
        sys.stderr.reconfigure(line_buffering=True)
        print("DEBUG: stderr reconfigured", file=sys.stderr, flush=True)
        
        # Create handler that writes to stderr (same as FastMCP/Uvicorn)
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        print("DEBUG: handler created", file=sys.stderr, flush=True)
        
        # Create logger
        logger = logging.getLogger("D365-MCP-Server")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False  # Prevent FastMCP from overriding
        print("DEBUG: logger configured", file=sys.stderr, flush=True)
        
        # Log startup banner
        logger.info("="*60)
        logger.info("D365 Field Service MCP Server Starting...")
        logger.info("="*60)
        
        # Validate environment variables
        REQUIRED_ENV_VARS = [
            "TENANT_ID",
            "CLIENT_ID", 
            "CLIENT_SECRET",
            "D365_URL",
            "D365_SCOPE"
        ]
        
        missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            logger.error("Please check your .env file or container environment variables")
            sys.exit(1)
        
        logger.info("✓ All required environment variables present")
        
        print("="*80, file=sys.stderr, flush=True)
        print("DEBUG: setup_logging() COMPLETED SUCCESSFULLY", file=sys.stderr, flush=True)
        print("="*80, file=sys.stderr, flush=True)
        
    except Exception as e:
        print("="*80, file=sys.stderr, flush=True)
        print(f"ERROR: setup_logging() FAILED: {e}", file=sys.stderr, flush=True)
        print("="*80, file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise


# ============================================================================
# Load Environment Variables
# ============================================================================
load_dotenv()

# ============================================================================
# Initialize FastMCP Server
# ============================================================================
mcp = FastMCP("D365 Field Service")
if logger:
    logger.info("✓ FastMCP server initialized")

# Initialize authenticator (handles OAuth2 tokens)
authenticator = D365Authenticator(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("D365_SCOPE"),
    verbose=False
)
if logger:
    logger.info("✓ D365 authenticator initialized")

# Initialize D365 client (handles API calls)
d365_client = D365Client(
    base_url=os.getenv("D365_URL"),
    authenticator=authenticator,
    verbose=False
)
if logger:
    logger.info(f"✓ D365 client initialized (URL: {os.getenv('D365_URL')})")


# ============================================================================
# INTERNAL FUNCTIONS (Business Logic)
# These can be called by BOTH MCP tools AND custom API
# ============================================================================

# D365 Work Order Status Codes (statuscode field)
# These are the integer values D365 expects for the statuscode field
STATUS_CODE_MAP = {
    "unscheduled": 690970000,
    "scheduled": 690970001,
    "in progress": 690970002,
    "completed": 690970003,
    "canceled": 690970004,
    "open": 690970000,  # Alias for unscheduled
}

async def _get_work_orders_internal(
    status: Optional[str] = None,
    max_results: int = 10,
    service_account_name: Optional[str] = None,
    include_count: bool = True
) -> Dict[str, Any]:
    """
    Internal function to get work orders with count metadata.
    
    Returns:
        Dictionary with:
        - work_orders: List of work order dictionaries
        - total_count: Total number of work orders matching the filter (if include_count=True)
        - returned_count: Number of work orders returned in this response
    """
    if logger:
        logger.info("="*60)
        logger.info("TOOL CALLED: get_work_orders")
        logger.info(f"  Arguments: status={status}, max_results={max_results}, service_account_name={service_account_name}, include_count={include_count}")
    
    try:
        filters = []
        
        # Handle status filter
        if status:
            # Map status name to integer code
            status_lower = status.lower().strip()
            status_code = STATUS_CODE_MAP.get(status_lower)
            
            if status_code is not None:
                filters.append(f"msdyn_systemstatus eq {status_code}")
                if logger:
                    logger.info(f"  Filter: status = '{status}' (code: {status_code})")
            else:
                if logger:
                    logger.warning(f"  Unknown status '{status}', querying without filter")
                    logger.info(f"  Valid statuses: {', '.join(STATUS_CODE_MAP.keys())}")
        
        # Handle service account name filter
        if service_account_name:
            if logger:
                logger.info(f"  Looking up service account: '{service_account_name}'...")
            
            # First, find the account by name
            accounts = await d365_client.query_accounts(
                filter_query=f"name eq '{service_account_name}'",
                top=1
            )
            
            if accounts and len(accounts) > 0:
                account_id = accounts[0].get('accountid')
                if account_id:
                    # Filter work orders by this account's GUID
                    filters.append(f"_msdyn_serviceaccount_value eq {account_id}")
                    if logger:
                        logger.info(f"  Filter: service_account_id = {account_id}")
                else:
                    if logger:
                        logger.warning(f"  Account '{service_account_name}' found but has no ID")
            else:
                if logger:
                    logger.warning(f"  No account found with name '{service_account_name}', querying without account filter")
        
        if logger:
            logger.info("  Querying D365 Field Service...")
        
        # Query with count metadata
        result = await d365_client.query_work_orders(
            filter_query=" and ".join(filters) if filters else None,
            top=min(max_results, 100),
            include_count=include_count
        )
        
        # Build response with metadata
        response = {
            "work_orders": result["value"],
            "returned_count": result["returned_count"]
        }
        
        # Add total count if available
        if "total_count" in result:
            response["total_count"] = result["total_count"]
            if logger:
                logger.info(f"  ✓ Success: Retrieved {result['returned_count']} of {result['total_count']} work orders")
        else:
            if logger:
                logger.info(f"  ✓ Success: Retrieved {result['returned_count']} work orders")
        
        logger.info("="*60)
        return response
        
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Error: {str(e)}")
            logger.info("="*60)
        return {
            "error": str(e),
            "message": "Failed to retrieve work orders. Check your D365 connection and credentials."
        }


async def _get_work_order_details_internal(work_order_id: str) -> Dict[str, Any]:
    """Internal function to get work order details - supports GUID or name lookup"""
    if logger:
        logger.info("="*60)
        logger.info("TOOL CALLED: get_work_order_details")
        logger.info(f"  Arguments: work_order_id={work_order_id}")
    
    try:
        # Check if it's a GUID format (contains dashes)
        is_guid = '-' in work_order_id
        
        if is_guid:
            # Direct lookup by GUID
            if logger:
                logger.info("  Fetching work order by GUID...")
            result = await d365_client.get_work_order_by_id(work_order_id)
        else:
            # Search by name first
            if logger:
                logger.info(f"  Searching for work order by name: '{work_order_id}'...")
            
            # Query by name
            search_results = await d365_client.query_work_orders(
                filter_query=f"msdyn_name eq '{work_order_id}'",
                top=1,
                include_count=False
            )
            
            # Extract work orders from response
            items = search_results.get("value", [])
            if not items or len(items) == 0:
                if logger:
                    logger.warning(f"  No work order found with name '{work_order_id}'")
                return {
                    "error": "Work order not found",
                    "message": f"No work order found with name '{work_order_id}'. Please provide the exact work order name or GUID."
                }
            
            # Get full details using the found GUID
            found_id = items[0].get('msdyn_workorderid')
            if logger:
                logger.info(f"  Found work order, fetching full details (ID: {found_id})...")
            result = await d365_client.get_work_order_by_id(found_id)
        
        if logger:
            logger.info(f"  ✓ Success: Retrieved work order '{result.get('msdyn_name', 'Unknown')}'")
            logger.info("="*60)
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Error: {str(e)}")
            logger.info("="*60)
        return {
            "error": str(e),
            "message": f"Failed to retrieve work order '{work_order_id}'. Verify the name or ID is correct."
        }


async def _list_field_technicians_internal(max_results: int = 10) -> List[Dict[str, Any]]:
    """Internal function to list field technicians"""
    if logger:
        logger.info("="*60)
        logger.info("TOOL CALLED: list_field_technicians")
        logger.info(f"  Arguments: max_results={max_results}")
    
    try:
        if logger:
            logger.info("  Querying bookable resources...")
        result = await d365_client.query_bookable_resources(top=max_results)
        
        if logger:
            logger.info(f"  ✓ Success: Retrieved {len(result)} technicians")
            logger.info("="*60)
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Error: {str(e)}")
            logger.info("="*60)
        return {
            "error": str(e),
            "message": "Failed to retrieve field technicians."
        }


async def _list_service_accounts_internal(max_results: int = 10) -> List[Dict[str, Any]]:
    """Internal function to list service accounts"""
    if logger:
        logger.info("="*60)
        logger.info("TOOL CALLED: list_service_accounts")
        logger.info(f"  Arguments: max_results={max_results}")
    
    try:
        if logger:
            logger.info("  Querying accounts...")
        result = await d365_client.query_accounts(top=max_results)
        
        if logger:
            logger.info(f"  ✓ Success: Retrieved {len(result)} accounts")
            logger.info("="*60)
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Error: {str(e)}")
            logger.info("="*60)
        return {
            "error": str(e),
            "message": "Failed to retrieve service accounts."
        }

async def _get_overdue_work_orders_internal(
    threshold_days: int = 0
) -> Dict[str, Any]:
    """
    Internal function to get overdue work orders with count metadata.
    
    Returns:
        Dictionary with:
        - overdue_work_orders: List of overdue work orders
        - overdue_count: Number of overdue work orders
        - total_active_count: Total number of active (non-completed/canceled) work orders
        - overdue_rate: Percentage of active work orders that are overdue
    """
    if logger:
        logger.info("="*60)
        logger.info("INTERNAL FUNCTION: _get_overdue_work_orders_internal")
        logger.info(f"  Arguments: threshold_days={threshold_days}")
    
    try:
        # Get all non-completed/canceled work orders with count
        if logger:
            logger.info("  Querying D365 for active work orders...")
        
        result = await d365_client.query_work_orders(
            filter_query="msdyn_systemstatus ne 690970003 and msdyn_systemstatus ne 690970004",
            top=1000,
            include_count=True
        )
        
        work_orders = result.get("value", [])
        total_active_count = result.get("total_count", len(work_orders))
        
        if logger:
            logger.info(f"  Retrieved {len(work_orders)} active work orders")
            if "total_count" in result:
                logger.info(f"  Total active work orders in system: {total_active_count}")
        
        overdue_wos = []
        now = datetime.now(timezone.utc)
        
        for wo in work_orders:
            created_on = wo.get('createdon')
            duration_minutes = wo.get('msdyn_totalestimatedduration')
            
            # Skip if missing required data
            if not created_on or not duration_minutes:
                continue
            
            try:
                # Parse ISO 8601 date
                created_dt = datetime.fromisoformat(created_on.replace('Z', '+00:00'))
                
                # Calculate expected completion
                duration_days = duration_minutes / 1440  # Convert minutes to days
                expected_completion = created_dt + timedelta(days=duration_days)
                
                # Check if overdue
                if now > expected_completion:
                    days_overdue = (now - expected_completion).days
                    
                    # Apply threshold filter
                    if days_overdue >= threshold_days:
                        # Add calculated fields
                        wo['expected_completion_date'] = expected_completion.isoformat()
                        wo['created_date_parsed'] = created_dt.isoformat()
                        wo['days_overdue'] = days_overdue
                        wo['is_critically_overdue'] = days_overdue > 7
                        wo['duration_days'] = round(duration_days, 2)
                        wo['expected_completion_formatted'] = expected_completion.strftime('%Y-%m-%d')
                        wo['created_date_formatted'] = created_dt.strftime('%Y-%m-%d')
                        
                        overdue_wos.append(wo)
            
            except Exception as e:
                if logger:
                    logger.warning(f"  Could not calculate overdue for WO {wo.get('msdyn_name')}: {e}")
                continue
        
        # Sort by most overdue first
        overdue_wos.sort(key=lambda x: x['days_overdue'], reverse=True)
        
        # Calculate overdue rate
        overdue_count = len(overdue_wos)
        overdue_rate = round((overdue_count / total_active_count * 100), 2) if total_active_count > 0 else 0
        
        if logger:
            logger.info(f"  ✓ Found {overdue_count} overdue work orders (threshold: {threshold_days}+ days)")
            logger.info(f"  📊 Overdue Rate: {overdue_rate}% ({overdue_count}/{total_active_count})")
            if overdue_wos:
                most_overdue = overdue_wos[0]
                logger.info(f"  ⚠️ Most overdue: {most_overdue.get('msdyn_name')} ({most_overdue['days_overdue']} days)")
            logger.info("="*60)
        
        return {
            "overdue_work_orders": overdue_wos,
            "overdue_count": overdue_count,
            "total_active_count": total_active_count,
            "overdue_rate": overdue_rate,
            "threshold_days": threshold_days
        }
    
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Error: {str(e)}")
            logger.info("="*60)
        return {
            "error": str(e),
            "message": "Failed to retrieve overdue work orders. Check your D365 connection and credentials."
        }


# ============================================================================
# MCP TOOL WRAPPERS (For /mcp endpoint - Auto-orchestration)
# ============================================================================

@mcp.tool()
async def get_work_orders(
    status: Optional[str] = None,
    max_results: int = 10,
    service_account_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve work orders from D365 Field Service.
    
    This tool queries the msdyn_workorder entity and returns a list of work orders.
    You can filter by status, customer/service account, and limit the number of results.
    
    Args:
        status: Optional work order status to filter by. Valid values:
                - "Unscheduled" or "Open" (not yet scheduled)
                - "Scheduled" (assigned to a technician)
                - "In Progress" (technician is working on it)
                - "Completed" (work is finished)
                - "Canceled" (work order was canceled)
        max_results: Maximum number of work orders to return (default: 10, max: 100)
        service_account_name: Optional customer/service account name to filter by (e.g., "Cafe Duo")
    
    Returns:
        List of work order dictionaries
    """
    # Explicit logging in wrapper to verify tool execution
    if logger:
        logger.info("🔧 MCP TOOL WRAPPER: get_work_orders called")
    return await _get_work_orders_internal(status, max_results, service_account_name)


@mcp.tool()
async def get_work_order_details(work_order_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific work order.
    
    This tool can find work orders by either their name or GUID.
    If you provide a work order name (e.g., "Sample_WO00018"), it will search for it and return the details.
    If you provide a GUID (e.g., "07b3e2b5-0adb-f011-8544-002248ebb512"), it will look it up directly.
    
    Args:
        work_order_id: Work order name (e.g., "Sample_WO00018") or GUID (msdyn_workorderid)
    
    Returns:
        Dictionary with work order details including name, status, service account, bookings, etc.
    """
    # Explicit logging in wrapper to verify tool execution
    if logger:
        logger.info("🔧 MCP TOOL WRAPPER: get_work_order_details called")
    return await _get_work_order_details_internal(work_order_id)


@mcp.tool()
async def list_field_technicians(max_results: int = 10) -> List[Dict[str, Any]]:
    """
    List available field technicians (bookable resources).
    
    Args:
        max_results: Maximum number of technicians to return (default: 10)
    
    Returns:
        List of technician dictionaries
    """
    # Explicit logging in wrapper to verify tool execution
    if logger:
        logger.info("🔧 MCP TOOL WRAPPER: list_field_technicians called")
    return await _list_field_technicians_internal(max_results)


@mcp.tool()
async def list_service_accounts(max_results: int = 10) -> List[Dict[str, Any]]:
    """
    List service accounts (customers) in D365 Field Service.
    
    Args:
        max_results: Maximum number of accounts to return (default: 10)
    
    Returns:
        List of account dictionaries
    """
    # Explicit logging in wrapper to verify tool execution
    if logger:
        logger.info("🔧 MCP TOOL WRAPPER: list_service_accounts called")
    return await _list_service_accounts_internal(max_results)


@mcp.tool()
async def get_overdue_work_orders(
    threshold_days: int = 0
) -> List[Dict[str, Any]]:
    """
    Get work orders that are overdue based on created date + total estimated duration.
    
    A work order is considered overdue if:
    - Current date > (Created Date + Estimated Duration)
    - Status is not "Completed" or "Canceled"
    
    Args:
        threshold_days: Minimum days overdue to include (0 = any overdue, 7 = only 1+ week overdue)
    
    Returns:
        List of overdue work orders sorted by most overdue first, with calculated fields:
        - expected_completion_date: When the work order should have been completed
        - days_overdue: Number of days past the expected completion date
        - is_critically_overdue: True if overdue by more than 7 days
        - duration_days: Original estimated duration in days
    
    Example queries:
        - "Show me overdue work orders"
        - "Which work orders are late?"
        - "Find work orders overdue by more than a week"
    """
    return await _get_overdue_work_orders_internal(threshold_days=threshold_days)


# ============================================================================
# CUSTOM API ENDPOINTS (For /tools/call - Agent-Topic)
# Separate FastAPI app for Custom API (runs on port 8001)
# ============================================================================

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


# Create Custom API FastAPI app (separate from FastMCP)
custom_api = FastAPI(title="D365 MCP Custom API")


@custom_api.get("/health")
async def health_check():
    """Health check endpoint"""
    if logger:
        logger.info("Health check requested")
    return {"status": "healthy", "service": "D365 MCP Server"}


@custom_api.post("/tools/call")
async def call_tool_direct(request: ToolCallRequest):
    """
    Direct tool invocation endpoint for Copilot Studio Agent-Topic.
    No MCP session management - just call tools directly.
    
    Normalizes parameter names for compatibility with Power Automate Flow.
    """
    if logger:
        logger.info("="*60)
        logger.info("CUSTOM API CALLED: /tools/call")
        logger.info(f"  Tool: {request.tool_name}")
        logger.info(f"  Arguments: {request.arguments}")
    
    try:
        tool_name = request.tool_name
        arguments = request.arguments.copy()  # Make a copy to modify
        
        # Normalize parameter names for compatibility with Flow
        normalizations = []
        
        # Flow might send 'limit' but our functions expect 'max_results'
        if 'limit' in arguments and 'max_results' not in arguments:
            arguments['max_results'] = arguments.pop('limit')
            normalizations.append(f"'limit' → 'max_results' = {arguments['max_results']}")
        
        # Flow might send 'customer_name' or 'account_name' instead of 'service_account_name'
        if 'customer_name' in arguments and 'service_account_name' not in arguments:
            arguments['service_account_name'] = arguments.pop('customer_name')
            normalizations.append(f"'customer_name' → 'service_account_name' = {arguments['service_account_name']}")
        
        if 'account_name' in arguments and 'service_account_name' not in arguments:
            arguments['service_account_name'] = arguments.pop('account_name')
            normalizations.append(f"'account_name' → 'service_account_name' = {arguments['service_account_name']}")
        
        if normalizations and logger:
            logger.info(f"  Normalized parameters: {'; '.join(normalizations)}")
        
        # Route to appropriate internal function
        if tool_name == "get_work_orders":
            result = await _get_work_orders_internal(**arguments)
        elif tool_name == "get_work_order_details":
            result = await _get_work_order_details_internal(**arguments)
        elif tool_name == "list_field_technicians":
            result = await _list_field_technicians_internal(**arguments)
        elif tool_name == "list_service_accounts":
            result = await _list_service_accounts_internal(**arguments)
        elif tool_name == "get_overdue_work_orders":
            result = await _get_overdue_work_orders_internal(**arguments)
        else:
            if logger:
                logger.error(f"  ✗ Unknown tool: {tool_name}")
                logger.info("="*60)
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        if logger:
            logger.info(f"  ✓ Tool execution completed")
            logger.info("="*60)
        return {"result": result}
        
    except TypeError as e:
        if logger:
            logger.error(f"  ✗ Invalid arguments: {str(e)}")
            logger.info("="*60)
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")
    except Exception as e:
        if logger:
            logger.error(f"  ✗ Tool execution error: {str(e)}")
            logger.info("="*60)
        raise HTTPException(status_code=500, detail=f"Tool execution error: {str(e)}")


# ============================================================================
# DUAL SERVER MODE
# ============================================================================

def main():
    """
    Main entry point - supports multiple transport modes:
    - STDIO: Default FastMCP for Claude Desktop
    - HTTP: Dual-port servers (FastMCP on 8000 + Custom API on 8001)
           Nginx reverse proxy routes both through port 8080
    """
    print("="*80, file=sys.stderr, flush=True)
    print("DEBUG: main() CALLED", file=sys.stderr, flush=True)
    print("="*80, file=sys.stderr, flush=True)
    
    # Configure logging FIRST - before anything else!
    print("DEBUG: About to call setup_logging()", file=sys.stderr, flush=True)
    setup_logging()
    print("DEBUG: setup_logging() returned successfully", file=sys.stderr, flush=True)
    
    try:
        transport = os.getenv("TRANSPORT", "stdio").lower()
        
        if transport == "http":
            # HTTP mode - Run BOTH servers on different ports
            import threading
            
            port_mcp = int(os.getenv("API_PORT", "8000"))
            port_custom = int(os.getenv("API_PORT_CUSTOM", "8001"))
            host = os.getenv("API_HOST", "0.0.0.0")
            
            if logger:
                logger.info("="*60)
                logger.info("🌐 Starting DUAL-PORT mode (with nginx proxy)")
                logger.info(f"📡 FastMCP (internal): http://{host}:{port_mcp}")
                logger.info(f"📡 Custom API (internal): http://{host}:{port_custom}")
                logger.info(f"🔀 Nginx proxy: Port 8080 → routes to both")
                logger.info("")
                logger.info("ℹ️  External routing (via nginx):")
                logger.info(f"   /mcp/* → FastMCP (port {port_mcp})")
                logger.info(f"   /tools/* → Custom API (port {port_custom})")
                logger.info(f"   /health → Custom API (port {port_custom})")
                logger.info("="*60)
            
            # Start FastMCP in background thread
            def run_fastmcp():
                if logger:
                    logger.info(f"Starting FastMCP server on port {port_mcp}...")
                mcp.run(transport="http", host=host, port=port_mcp)
            
            mcp_thread = threading.Thread(target=run_fastmcp, daemon=True)
            mcp_thread.start()
            
            if logger:
                logger.info(f"✅ FastMCP started on port {port_mcp}")
                # Run custom API in main thread
                logger.info(f"✅ Starting Custom API on port {port_custom}")
                logger.info("="*60)
                logger.info("Server is ready to accept requests")
                logger.info("="*60)
            uvicorn.run(custom_api, host=host, port=port_custom)
            
        else:
            # STDIO mode - Standard FastMCP for Claude Desktop
            if logger:
                logger.info("🖥️  Starting MCP server in STDIO mode (for Claude Desktop)")
                logger.info("="*60)
            mcp.run()
        
    except KeyboardInterrupt:
        if logger:
            logger.info("Server stopped by user")
    except Exception as e:
        if logger:
            logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    print("="*80, file=sys.stderr, flush=True)
    print("DEBUG: __main__ ENTRY POINT", file=sys.stderr, flush=True)
    print("="*80, file=sys.stderr, flush=True)
    main()
