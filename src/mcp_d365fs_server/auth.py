"""
OAuth2 Authentication Module for Dynamics 365 - ENCODING-SAFE VERSION

This module handles authentication with Azure AD using the MSAL library.
FIXED: All output is ASCII-safe and goes to stderr to avoid STDIO interference.
"""

import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from msal import ConfidentialClientApplication


class D365Authenticator:
    """
    Handles OAuth2 authentication with Azure AD for D365 access.
    
    Uses MSAL (Microsoft Authentication Library) for client credentials flow.
    """
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: str,
        verbose: bool = False
    ):
        """
        Initialize the authenticator with Azure AD credentials.
        
        Args:
            tenant_id: Azure AD tenant ID (GUID)
            client_id: App registration application (client) ID
            client_secret: App registration client secret
            scope: API scope (e.g., https://yourorg.crm.dynamics.com/.default)
            verbose: If True, print diagnostic messages to stderr (default: False)
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.verbose = verbose
        
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
        
        if self.verbose:
            print("D365Authenticator initialized", file=sys.stderr)
            print(f"  Tenant ID: {tenant_id}", file=sys.stderr)
            print(f"  Client ID: {client_id}", file=sys.stderr)
            print(f"  Scope: {scope}", file=sys.stderr)
    
    
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
        """
        # Check if we have a valid cached token
        if self._is_token_valid():
            if self.verbose:
                print("Using cached access token", file=sys.stderr)
            return self._token_cache["access_token"]
        
        # Need to acquire a new token
        if self.verbose:
            print("Acquiring new access token from Azure AD...", file=sys.stderr)
        
        try:
            # Use MSAL to acquire token with client credentials
            result = self.app.acquire_token_for_client(scopes=[self.scope])
            
            # Check if token acquisition was successful
            if "access_token" in result:
                # Cache the token with expiration
                self._cache_token(result)
                
                if self.verbose:
                    print("Successfully acquired access token", file=sys.stderr)
                    print(f"  Expires in: {result.get('expires_in', 0)} seconds", file=sys.stderr)
                
                return result["access_token"]
            else:
                # Token acquisition failed
                error = result.get("error", "Unknown error")
                error_description = result.get("error_description", "No description")
                
                print(f"Failed to acquire token: {error}", file=sys.stderr)
                print(f"  Description: {error_description}", file=sys.stderr)
                
                return None
                
        except Exception as e:
            print(f"Exception during token acquisition: {e}", file=sys.stderr)
            return None
    
    
    def _is_token_valid(self) -> bool:
        """
        Check if the cached token is still valid.
        
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
        
        if self.verbose:
            print(f"Token cached until {expiration.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    
    
    def clear_cache(self) -> None:
        """Clear the cached token."""
        self._token_cache = None
        if self.verbose:
            print("Token cache cleared", file=sys.stderr)
    
    
    def get_token_info(self) -> Dict[str, Any]:
        """
        Get information about the current token.
        
        Returns:
            Dictionary with token information
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
    Run with: python -m src.mcp_d365fs_server.auth
    """
    from dotenv import load_dotenv
    
    print("=" * 60, file=sys.stderr)
    print("   D365 Authentication Test", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scope = os.getenv("D365_SCOPE")
    
    # Validate credentials are present
    if not all([tenant_id, client_id, client_secret, scope]):
        print("Missing credentials in .env file", file=sys.stderr)
        print("  Required: TENANT_ID, CLIENT_ID, CLIENT_SECRET, D365_SCOPE", file=sys.stderr)
        return
    
    print("Configuration loaded from .env", file=sys.stderr)
    print(f"  Tenant ID: {tenant_id}", file=sys.stderr)
    print(f"  Client ID: {client_id}", file=sys.stderr)
    print(f"  Scope: {scope}", file=sys.stderr)
    print(file=sys.stderr)
    
    # Create authenticator with verbose mode for testing
    print("Creating authenticator...", file=sys.stderr)
    authenticator = D365Authenticator(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        verbose=True  # Enable verbose mode for testing
    )
    print(file=sys.stderr)
    
    # Test token acquisition
    print("Testing token acquisition...", file=sys.stderr)
    token = await authenticator.get_token()
    print(file=sys.stderr)
    
    if token:
        print("SUCCESS! Authentication working correctly", file=sys.stderr)
        print(f"  Token: {token[:50]}...", file=sys.stderr)
        print(f"  Token length: {len(token)} characters", file=sys.stderr)
        
        # Show token info
        info = authenticator.get_token_info()
        print(file=sys.stderr)
        print("Token Information:", file=sys.stderr)
        print(f"  Valid: {info['is_valid']}", file=sys.stderr)
        print(f"  Expires in: {info['expires_in']} seconds", file=sys.stderr)
        print(f"  Expiration: {info['expiration']}", file=sys.stderr)
        
        print(file=sys.stderr)
        print("You can now use this authenticator with d365_client!", file=sys.stderr)
    else:
        print("FAILED! Could not acquire token", file=sys.stderr)
        print(file=sys.stderr)
        print("Troubleshooting:", file=sys.stderr)
        print("  1. Verify credentials in .env are correct", file=sys.stderr)
        print("  2. Check App Registration has API permissions", file=sys.stderr)
        print("  3. Verify Admin Consent was granted", file=sys.stderr)
        print("  4. Verify D365_SCOPE is correct", file=sys.stderr)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_authentication())
