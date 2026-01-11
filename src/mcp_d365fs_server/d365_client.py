"""
D365 Client Module - FIXED VERSION

This module provides a client for interacting with D365 Field Service OData API.
Uses minimal, guaranteed-to-exist fields to avoid field name errors.
"""

import os
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
        api_version: str = "v9.2"
    ):
        """
        Initialize D365 client.
        
        Args:
            base_url: D365 instance URL (e.g., https://yourorg.crm.dynamics.com)
            authenticator: D365Authenticator instance for getting tokens
            api_version: OData API version (default: v9.2)
        """
        self.base_url = base_url.rstrip('/')
        self.authenticator = authenticator
        self.api_version = api_version
        self.api_endpoint = f"{self.base_url}/api/data/{api_version}"
        
        # HTTP client for making requests
        self._client: Optional[httpx.AsyncClient] = None
        
        print(f"✅ D365Client initialized")
        print(f"   Base URL: {self.base_url}")
        print(f"   API Version: {api_version}")
        print(f"   API Endpoint: {self.api_endpoint}")
    
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
            raise Exception(error_msg) from e
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}") from e
    
    async def query_work_orders(
        self,
        filter_query: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
        top: int = 10,
        order_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query work orders from D365 Field Service.
        
        FIXED VERSION: Uses only guaranteed system fields that exist in all D365 instances.
        
        Args:
            filter_query: OData filter expression (e.g., "msdyn_systemstatus eq 690970000")
            select_fields: List of fields to return (default: minimal guaranteed fields)
            top: Number of records to return (max 5000)
            order_by: Field to sort by (e.g., "createdon desc")
        
        Returns:
            List of work order dictionaries
        """
        # Use ONLY guaranteed system fields that exist in ALL D365 instances
        if not select_fields:
            select_fields = [
                "msdyn_workorderid",  # Primary key - always exists
                "msdyn_name",          # Name field - always exists  
                "createdon",           # System field - always exists
                "modifiedon"           # System field - always exists
            ]
        
        # Build OData query URL
        url = f"{self.api_endpoint}/msdyn_workorders"
        
        params = {
            "$select": ",".join(select_fields),
            "$top": str(top)
        }
        
        if filter_query:
            params["$filter"] = filter_query
        
        if order_by:
            params["$orderby"] = order_by
        else:
            params["$orderby"] = "createdon desc"  # Default: newest first
        
        # Make request
        result = await self._make_request("GET", url, params=params)
        
        return result.get("value", [])
    
    async def get_work_order_by_id(
        self,
        work_order_id: str,
        select_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get a specific work order by ID.
        
        Args:
            work_order_id: The GUID of the work order
            select_fields: List of fields to return (default: minimal fields)
        
        Returns:
            Work order dictionary
        """
        # Use minimal fields by default
        if not select_fields:
            select_fields = [
                "msdyn_workorderid",
                "msdyn_name",
                "createdon",
                "modifiedon"
            ]
        
        url = f"{self.api_endpoint}/msdyn_workorders({work_order_id})"
        
        params = {
            "$select": ",".join(select_fields)
        }
        
        return await self._make_request("GET", url, params=params)
    
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
    
    print("=" * 60)
    print("   D365 Client Test")
    print("=" * 60)
    print()
    
    # Load configuration
    d365_url = os.getenv("D365_URL")
    print(f"📋 Configuration loaded")
    print(f"   D365 URL: {d365_url}")
    print()
    
    # Create authenticator
    print("🔧 Creating authenticator...")
    authenticator = D365Authenticator(
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scope=os.getenv("D365_SCOPE")
    )
    print()
    
    # Create D365 client
    print("🔧 Creating D365 client...")
    client = D365Client(
        base_url=d365_url,
        authenticator=authenticator
    )
    print()
    
    try:
        # Test 1: Query work orders
        print("📊 Querying work orders (top 5)...")
        try:
            work_orders = await client.query_work_orders(top=5)
            print(f"✅ Retrieved {len(work_orders)} work orders")
            for wo in work_orders[:3]:  # Show first 3
                print(f"   - {wo.get('msdyn_name', 'Unnamed')} (ID: {wo.get('msdyn_workorderid', 'N/A')[:8]}...)")
        except Exception as e:
            print(f"❌ Error querying work orders: {e}")
        print()
        
        # Test 2: Query bookable resources
        print("👥 Querying bookable resources (top 5)...")
        try:
            resources = await client.query_bookable_resources(top=5)
            print(f"✅ Retrieved {len(resources)} resources")
            for res in resources[:3]:  # Show first 3
                print(f"   - {res.get('name', 'Unnamed')} (ID: {res.get('bookableresourceid', 'N/A')[:8]}...)")
        except Exception as e:
            print(f"❌ Error querying resources: {e}")
        print()
        
        # Test 3: Query accounts
        print("🏢 Querying service accounts (top 5)...")
        try:
            accounts = await client.query_accounts(top=5)
            print(f"✅ Retrieved {len(accounts)} accounts")
            for acc in accounts[:3]:  # Show first 3
                print(f"   - {acc.get('name', 'Unnamed')} (ID: {acc.get('accountid', 'N/A')[:8]}...)")
        except Exception as e:
            print(f"❌ Error querying accounts: {e}")
        print()
        
    finally:
        # Clean up
        await client.close()
        print("✅ D365Client closed")
    
    print()
    print("🎉 Test complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_d365_client())
