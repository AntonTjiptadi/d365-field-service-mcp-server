"""
OAuth2 Authentication Module for Dynamics 365

This module handles authentication with Azure AD using the MSAL library.
It manages access tokens for D365 API calls using the client credentials flow.

Main responsibilities:
- Authenticate with Azure AD using client credentials (App Registration)
- Acquire and cache access tokens
- Provide tokens to d365_client for API requests
- Handle token refresh automatically

OAuth2 Flow Used: Client Credentials Flow
- For server-to-server authentication
- No user interaction required
- Uses CLIENT_ID, CLIENT_SECRET, TENANT_ID from .env
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from msal import ConfidentialClientApplication


class D365Authenticator:
    """
    Handles OAuth2 authentication with Azure AD for D365 access.
    
    This class uses MSAL (Microsoft Authentication Library) to:
    1. Create a confidential client application
    2. Acquire access tokens using client credentials
    3. Cache tokens to avoid unnecessary auth calls
    4. Automatically refresh tokens when needed
    
    Attributes:
        tenant_id: Azure AD tenant ID
        client_id: App registration client ID
        client_secret: App registration client secret
        scope: D365 API scope (usually https://yourorg.crm.dynamics.com/.default)
        app: MSAL ConfidentialClientApplication instance
        _token_cache: Cached token with expiration
    """
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: str
    ):
        """
        Initialize the authenticator with Azure AD credentials.
        
        Args:
            tenant_id: Azure AD tenant ID (GUID)
            client_id: App registration application (client) ID
            client_secret: App registration client secret
            scope: API scope (e.g., https://yourorg.crm.dynamics.com/.default)
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        
        # Build the authority URL for Azure AD
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        
        # Create MSAL confidential client application
        self.app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=self.authority
        )
        
        # Token cache (stores token and expiration time)
        self._token_cache: Optional[Dict[str, Any]] = None
        
        print(f"✅ D365Authenticator initialized")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Client ID: {client_id}")
        print(f"   Scope: {scope}")
    
    
    async def get_token(self) -> Optional[str]:
        """
        Get a valid access token for D365 API.
        
        This method:
        1. Checks if we have a cached token that's still valid
        2. If not, acquires a new token from Azure AD
        3. Caches the new token with expiration time
        4. Returns the access token
        
        Returns:
            Access token string if successful, None if authentication fails
        
        Example:
            token = await authenticator.get_token()
            if token:
                headers = {"Authorization": f"Bearer {token}"}
        """
        # Check if we have a valid cached token
        if self._is_token_valid():
            print("🔑 Using cached access token")
            return self._token_cache["access_token"]
        
        # Need to acquire a new token
        print("🔄 Acquiring new access token from Azure AD...")
        
        try:
            # Use MSAL to acquire token with client credentials
            result = self.app.acquire_token_for_client(scopes=[self.scope])
            
            # Check if token acquisition was successful
            if "access_token" in result:
                # Cache the token with expiration
                self._cache_token(result)
                
                print("✅ Successfully acquired access token")
                print(f"   Token expires in: {result.get('expires_in', 0)} seconds")
                
                return result["access_token"]
            else:
                # Token acquisition failed
                error = result.get("error", "Unknown error")
                error_description = result.get("error_description", "No description")
                
                print(f"❌ Failed to acquire token")
                print(f"   Error: {error}")
                print(f"   Description: {error_description}")
                
                return None
                
        except Exception as e:
            print(f"❌ Exception during token acquisition: {e}")
            return None
    
    
    def _is_token_valid(self) -> bool:
        """
        Check if the cached token is still valid.
        
        A token is considered valid if:
        1. We have a cached token
        2. The token hasn't expired yet (with 5-minute buffer)
        
        Returns:
            True if cached token is valid, False otherwise
        """
        if not self._token_cache:
            return False
        
        # Check if token has expired (with 5-minute buffer)
        expiration = self._token_cache.get("expiration")
        if not expiration:
            return False
        
        # Add 5-minute buffer to avoid using tokens about to expire
        buffer = timedelta(minutes=5)
        now = datetime.now()
        
        return now < (expiration - buffer)
    
    
    def _cache_token(self, token_result: Dict[str, Any]) -> None:
        """
        Cache the access token with expiration time.
        
        Args:
            token_result: Token result from MSAL containing access_token and expires_in
        """
        # Get expiration time (in seconds from now)
        expires_in = token_result.get("expires_in", 3600)  # Default 1 hour
        
        # Calculate expiration datetime
        expiration = datetime.now() + timedelta(seconds=expires_in)
        
        # Store in cache
        self._token_cache = {
            "access_token": token_result["access_token"],
            "expires_in": expires_in,
            "expiration": expiration,
            "token_type": token_result.get("token_type", "Bearer")
        }
        
        print(f"💾 Token cached until {expiration.strftime('%Y-%m-%d %H:%M:%S')}")
    
    
    def clear_cache(self) -> None:
        """
        Clear the cached token.
        
        Call this if you want to force a new token acquisition,
        for example after configuration changes or authentication errors.
        """
        self._token_cache = None
        print("🗑️  Token cache cleared")
    
    
    def get_token_info(self) -> Dict[str, Any]:
        """
        Get information about the current token.
        
        Useful for debugging and monitoring.
        
        Returns:
            Dictionary with token information:
            - has_token: Whether a token is cached
            - is_valid: Whether the cached token is still valid
            - expires_in: Seconds until expiration (if valid)
            - expiration: Expiration datetime (if valid)
        """
        if not self._token_cache:
            return {
                "has_token": False,
                "is_valid": False,
                "expires_in": None,
                "expiration": None
            }
        
        is_valid = self._is_token_valid()
        expiration = self._token_cache.get("expiration")
        
        if is_valid and expiration:
            expires_in = (expiration - datetime.now()).total_seconds()
        else:
            expires_in = 0
        
        return {
            "has_token": True,
            "is_valid": is_valid,
            "expires_in": int(expires_in),
            "expiration": expiration.isoformat() if expiration else None
        }


# ============================================================================
# Test Function (for standalone testing)
# ============================================================================

async def test_authentication():
    """
    Test the D365 authentication.
    
    This function can be run standalone to verify your credentials work:
        python -m src.mcp_d365fs_server.auth
    
    It will:
    1. Load credentials from .env
    2. Create authenticator
    3. Attempt to get a token
    4. Display results
    """
    from dotenv import load_dotenv
    
    print("=" * 60)
    print("   D365 Authentication Test")
    print("=" * 60)
    print()
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scope = os.getenv("D365_SCOPE")
    
    # Validate credentials are present
    if not all([tenant_id, client_id, client_secret, scope]):
        print("❌ Missing credentials in .env file")
        print("   Required: TENANT_ID, CLIENT_ID, CLIENT_SECRET, D365_SCOPE")
        return
    
    print("📋 Credentials loaded from .env")
    print(f"   Tenant ID: {tenant_id}")
    print(f"   Client ID: {client_id}")
    print(f"   Client Secret: {'*' * len(client_secret)}")
    print(f"   Scope: {scope}")
    print()
    
    # Create authenticator
    print("🔧 Creating authenticator...")
    authenticator = D365Authenticator(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope
    )
    print()
    
    # Test token acquisition
    print("🔐 Testing token acquisition...")
    token = await authenticator.get_token()
    print()
    
    if token:
        print("✅ SUCCESS! Authentication working correctly")
        print(f"   Token: {token[:50]}...")
        print(f"   Token length: {len(token)} characters")
        
        # Show token info
        info = authenticator.get_token_info()
        print()
        print("📊 Token Information:")
        print(f"   Valid: {info['is_valid']}")
        print(f"   Expires in: {info['expires_in']} seconds")
        print(f"   Expiration: {info['expiration']}")
        
        print()
        print("🎉 You can now use this authenticator with d365_client!")
    else:
        print("❌ FAILED! Could not acquire token")
        print()
        print("🔍 Troubleshooting:")
        print("   1. Verify credentials in .env are correct")
        print("   2. Check App Registration has API permissions")
        print("   3. Verify Admin Consent was granted")
        print("   4. Check TENANT_ID, CLIENT_ID, CLIENT_SECRET are correct")
        print("   5. Verify D365_SCOPE is correct (https://yourorg.crm.dynamics.com/.default)")


# Allow running as standalone module for testing
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_authentication())
