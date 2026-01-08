"""
Test Suite for MCP D365 Field Service Server

This package contains unit tests and integration tests for the MCP server.

Test modules:
- test_auth: OAuth2 authentication tests
- test_d365_client: D365 API client tests
- test_tools: MCP tool implementation tests
- test_models: Pydantic model validation tests

Run tests with:
    pytest
    pytest tests/
    pytest tests/test_auth.py
    pytest -v
    pytest -m unit
    pytest -m "not integration"
"""