"""
D365 Client Module - ENCODING-SAFE VERSION

This module provides a client for interacting with D365 Field Service OData API.
FIXED: All output is ASCII-safe and goes to stderr to avoid STDIO interference.
Uses minimal, guaranteed-to-exist fields to avoid field name errors.
"""

import os
import sys
from typing import Optional, List, Dict, Any
import httpx

from .auth import D365Authenticator


class D365Client:
    """
    Client for D365 Field Service OData API.
    
    This class handles:
    - Building OData query URLs
    - Making authenticated HTTP requests
    - Error handling and response parsing
    """
    
    def __init__(
        self,
        base_url: str,
        authenticator: D365Authenticator,
        api_version: str = "v9.2",
        verbose: bool = False
    ):
        """
        Initialize D365 client.
        
        Args:
            base_url: D365 instance URL (e.g., https://yourorg.crm.dynamics.com)
            authenticator: D365Authenticator instance for getting tokens
            api_version: OData API version (default: v9.2)
            verbose: If True, print diagnostic messages to stderr (default: False)
        """
        self.base_url = base_url.rstrip('/')
        self.authenticator = authenticator
        self.api_version = api_version
        self.api_endpoint = f"{self.base_url}/api/data/{api_version}"
        self.verbose = verbose
        
        # HTTP client for making requests
        self._client: Optional[httpx.AsyncClient] = None
        
        if self.verbose:
            print("D365Client initialized", file=sys.stderr)
            print(f"  Base URL: {self.base_url}", file=sys.stderr)
            print(f"  API Version: {api_version}", file=sys.stderr)
            print(f"  API Endpoint: {self.api_endpoint}", file=sys.stderr)
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close HTTP client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _get_headers(self) -> Dict[str, str]:
        """
        Build HTTP headers with authentication token.
        
        Returns:
            Dictionary of HTTP headers including Bearer token
        """
        token = await self.authenticator.get_token()
        if not token:
            raise Exception("Failed to get authentication token")
        
        return {
            "Authorization": f"Bearer {token}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to D365 API.
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            url: Full URL to request
            **kwargs: Additional arguments for httpx request
        
        Returns:
            Parsed JSON response
        
        Raises:
            Exception: If request fails
        """
        headers = await self._get_headers()
        client = await self._get_client()
        
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            
            response.raise_for_status()
            
            if response.status_code == 204:  # No Content
                return {}
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            error_msg = f"D365 API error ({e.response.status_code}): {e.response.text}"
            if self.verbose:
                print(error_msg, file=sys.stderr)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            if self.verbose:
                print(error_msg, file=sys.stderr)
            raise Exception(error_msg) from e
    
    async def query_work_orders(
        self,
        filter_query: Optional[str] = None,
        expand_service_account: bool = False,
        top: int = 10,
        include_count: bool = False
    ) -> Dict[str, Any]:
        """
        Query work orders with optional filtering and expansion.
    
        Args:
            filter_query: OData filter string
            expand_service_account: Whether to expand service account details
            top: Maximum number of records (use None for all records)
            include_count: Whether to include total count in response
        
        Returns:
            Dictionary with:
            - value: List of work orders
            - count: Total count (if include_count=True)
            - returned_count: Number of records returned
        """
        try:
            url = f"{self.api_endpoint}/msdyn_workorders"
            
            params = {
                "$select": "msdyn_workorderid,msdyn_name,createdon,modifiedon,msdyn_systemstatus,statuscode," \
                "msdyn_totalestimatedduration,_msdyn_serviceaccount_value",
                
                "$orderby": "createdon desc"
            }
            
            # Add top parameter if specified
            if top is not None:
                params["$top"] = str(top)
            
            # Add count parameter if requested
            if include_count:
                params["$count"] = "true"
            
            if filter_query:
                params["$filter"] = filter_query
            
            if expand_service_account:
                # IMPORTANT: Use lowercase logical name 'msdyn_serviceaccount'
                params["$expand"] = "msdyn_serviceaccount($select=name,accountid)"
            
            result = await self._make_request("GET", url, params=params)
            
            # Return structured response with metadata
            work_orders = result.get("value", [])
            response = {
                "value": work_orders,
                "returned_count": len(work_orders)
            }
            
            # Add total count if available
            if "@odata.count" in result:
                response["total_count"] = result["@odata.count"]
            
            return response
        
        except Exception as e:
            # Re-raise with more context
            raise Exception(f"D365 API query failed: {str(e)}")
    
    async def get_work_order_by_id(
    self,
    work_order_id: str,
    select_fields: Optional[List[str]] = None,
    expand_technician: bool = True
    ) -> Dict[str, Any]:
        """
        Get a specific work order by ID with optional technician info.
        """
        if not select_fields:
            select_fields = [
                "msdyn_workorderid",
                "msdyn_name",
                "createdon",
                "modifiedon"
            ]
        
        # Get basic work order info
        url = f"{self.api_endpoint}/msdyn_workorders"
        params = {
            "$select": ",".join(select_fields),
            "$filter": f"msdyn_workorderid eq {work_order_id}",
            "$top": "1"
        }
        
        result = await self._make_request("GET", url, params=params)
        items = result.get("value", [])
        if not items:
            raise Exception(f"Work order {work_order_id} not found")
        
        work_order = items[0]
        
        # Get bookings with technician info if requested
        if expand_technician:
            bookings_url = f"{self.api_endpoint}/bookableresourcebookings"
            bookings_params = {
                "$filter": f"_msdyn_workorder_value eq {work_order_id}",
                "$expand": "Resource($select=name,bookableresourceid)",
                "$select": "bookableresourcebookingid,name,starttime,endtime,duration"
            }
            
            bookings_result = await self._make_request("GET", bookings_url, params=bookings_params)
            work_order["bookings"] = bookings_result.get("value", [])
        
        return work_order
    
    async def get_work_order_by_name(
    self,
    work_order_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a work order by its name and return basic info.
        
        Args:
            work_order_name: The work order name (e.g., "Sample_WO00010")
        
        Returns:
            Dictionary with msdyn_workorderid and msdyn_name, or None if not found
        """
        try:
            url = f"{self.api_endpoint}/msdyn_workorders"
            
            params = {
                "$select": "msdyn_workorderid,msdyn_name",
                "$filter": f"msdyn_name eq '{work_order_name}'",
                "$top": "1"
            }
            
            result = await self._make_request("GET", url, params=params)
            items = result.get("value", [])
            
            return items[0] if items else None
            
        except Exception as e:
            raise Exception(f"Failed to lookup work order by name: {str(e)}")
    
    async def query_bookable_resources(
        self,
        filter_query: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
        top: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query bookable resources (field technicians).
        
        FIXED VERSION: Uses only guaranteed system fields.
        
        Args:
            filter_query: OData filter expression
            select_fields: List of fields to return (default: minimal fields)
            top: Number of records to return
        
        Returns:
            List of bookable resource dictionaries
        """
        # Use ONLY guaranteed system fields
        if not select_fields:
            select_fields = [
                "bookableresourceid",  # Primary key - always exists
                "name",                 # Name field - always exists
                "createdon",            # System field - always exists
                "modifiedon"            # System field - always exists
            ]
        
        url = f"{self.api_endpoint}/bookableresources"
        
        params = {
            "$select": ",".join(select_fields),
            "$top": str(top),
            "$orderby": "name asc"
        }
        
        if filter_query:
            params["$filter"] = filter_query
        
        result = await self._make_request("GET", url, params=params)
        
        return result.get("value", [])
    
    async def query_accounts(
        self,
        filter_query: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
        top: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query service accounts (customers).
        
        FIXED VERSION: Uses only guaranteed system fields.
        
        Args:
            filter_query: OData filter expression
            select_fields: List of fields to return (default: minimal fields)
            top: Number of records to return
        
        Returns:
            List of account dictionaries
        """
        # Use ONLY guaranteed system fields
        if not select_fields:
            select_fields = [
                "accountid",     # Primary key - always exists
                "name",          # Name field - always exists
                "createdon",     # System field - always exists
                "modifiedon"     # System field - always exists
            ]
        
        url = f"{self.api_endpoint}/accounts"
        
        params = {
            "$select": ",".join(select_fields),
            "$top": str(top),
            "$orderby": "name asc"
        }
        
        if filter_query:
            params["$filter"] = filter_query
        
        result = await self._make_request("GET", url, params=params)
        
        return result.get("value", [])


# ============================================================================
# Test Functions
# ============================================================================

async def test_d365_client():
    """Test D365 client with real API calls."""
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 60, file=sys.stderr)
    print("   D365 Client Test", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    
    # Load configuration
    d365_url = os.getenv("D365_URL")
    print("Configuration loaded", file=sys.stderr)
    print(f"  D365 URL: {d365_url}", file=sys.stderr)
    print(file=sys.stderr)
    
    # Create authenticator
    print("Creating authenticator...", file=sys.stderr)
    authenticator = D365Authenticator(
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scope=os.getenv("D365_SCOPE"),
        verbose=True
    )
    print(file=sys.stderr)
    
    # Create D365 client
    print("Creating D365 client...", file=sys.stderr)
    client = D365Client(
        base_url=d365_url,
        authenticator=authenticator,
        verbose=True
    )
    print(file=sys.stderr)
    
    try:
        # Test 1: Query work orders
        print("Querying work orders (top 5)...", file=sys.stderr)
        try:
            work_orders = await client.query_work_orders(top=5)
            print(f"Retrieved {len(work_orders)} work orders", file=sys.stderr)
            for wo in work_orders[:3]:  # Show first 3
                print(f"  - {wo.get('msdyn_name', 'Unnamed')} (ID: {wo.get('msdyn_workorderid', 'N/A')[:8]}...)", file=sys.stderr)
        except Exception as e:
            print(f"Error querying work orders: {e}", file=sys.stderr)
        print(file=sys.stderr)
        
        # Test 2: Query bookable resources
        print("Querying bookable resources (top 5)...", file=sys.stderr)
        try:
            resources = await client.query_bookable_resources(top=5)
            print(f"Retrieved {len(resources)} resources", file=sys.stderr)
            for res in resources[:3]:  # Show first 3
                print(f"  - {res.get('name', 'Unnamed')} (ID: {res.get('bookableresourceid', 'N/A')[:8]}...)", file=sys.stderr)
        except Exception as e:
            print(f"Error querying resources: {e}", file=sys.stderr)
        print(file=sys.stderr)
        
        # Test 3: Query accounts
        print("Querying service accounts (top 5)...", file=sys.stderr)
        try:
            accounts = await client.query_accounts(top=5)
            print(f"Retrieved {len(accounts)} accounts", file=sys.stderr)
            for acc in accounts[:3]:  # Show first 3
                print(f"  - {acc.get('name', 'Unnamed')} (ID: {acc.get('accountid', 'N/A')[:8]}...)", file=sys.stderr)
        except Exception as e:
            print(f"Error querying accounts: {e}", file=sys.stderr)
        print(file=sys.stderr)
        
    finally:
        # Clean up
        await client.close()
        print("D365Client closed", file=sys.stderr)
    
    print(file=sys.stderr)
    print("Test complete!", file=sys.stderr)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_d365_client())
