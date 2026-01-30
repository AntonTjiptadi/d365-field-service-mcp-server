"""
Minimal REST API for D365 Field Service - Copilot Studio Integration
Reuses existing auth.py and d365_client.py

This is a SEPARATE server from server.py:
- server.py = MCP Server for Claude Desktop (STDIO mode)
- rest_api.py = REST API for Copilot Studio (HTTP/REST mode)

Both servers share the same auth.py and d365_client.py code.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
from dotenv import load_dotenv

from .auth import D365Authenticator
from .d365_client import D365Client

# Load environment
load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="D365 Field Service API",
    description="Simple REST API for Copilot Studio integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize D365 client (same as MCP server)
authenticator = D365Authenticator(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("D365_SCOPE"),
    verbose=False
)

d365_client = D365Client(
    base_url=os.getenv("D365_URL"),
    authenticator=authenticator,
    verbose=False
)


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root - health check"""
    return {
        "service": "D365 Field Service API",
        "status": "healthy",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "service": "D365 Field Service API",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/api/work-orders")
async def get_work_orders(
    status: Optional[str] = Query(None, description="Filter by status (e.g., 'Open', 'In Progress')"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Get list of work orders
    
    Query Parameters:
    - status: Filter by work order status (optional)
    - limit: Maximum number of results (1-100, default: 10)
    
    Example: GET /api/work-orders?status=Open&limit=5
    """
    try:
        filters = []
        if status:
            filters.append(f"msdyn_systemstatus eq '{status}'")
        
        result = await d365_client.query_work_orders(
            filter_query=" and ".join(filters) if filters else None,
            top=limit
        )
        
        return {
            "success": True,
            "data": result,
            "count": len(result),
            "status_filter": status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/work-orders/{work_order_id}")
async def get_work_order_details(work_order_id: str):
    """
    Get details of a specific work order
    
    Path Parameters:
    - work_order_id: The unique identifier (GUID) of the work order
    
    Example: GET /api/work-orders/abc-123-guid
    """
    try:
        result = await d365_client.get_work_order_by_id(work_order_id)
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Work order not found: {str(e)}"
        )


@app.get("/api/technicians")
async def get_technicians(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Get list of field technicians (bookable resources)
    
    Query Parameters:
    - limit: Maximum number of results (1-100, default: 10)
    
    Example: GET /api/technicians?limit=20
    """
    try:
        result = await d365_client.query_bookable_resources(top=limit)
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts")
async def get_accounts(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Get list of service accounts (customers)
    
    Query Parameters:
    - limit: Maximum number of results (1-100, default: 10)
    
    Example: GET /api/accounts?limit=15
    """
    try:
        result = await d365_client.query_accounts(top=limit)
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Run server (for local development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    print(f"🚀 Starting D365 Field Service REST API on {host}:{port}")
    print(f"📚 API documentation: http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port, reload=True)
