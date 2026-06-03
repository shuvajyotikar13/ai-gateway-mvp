import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.gateway.router import ResilientStreamRouter

@pytest.mark.asyncio
@patch("httpx.AsyncClient.send")
async def test_router_transparent_failover_on_primary_429(mock_send):
    """
    Verifies that if the primary provider returns an immediate HTTP 429 status code, 
    the router catches the exception before sending headers and shifts to the fallback engine.
    """
    # 1. Setup mock response states mapping primary failure and secondary success
    mock_response_primary = AsyncMock(spec=httpx.Response)
    mock_response_primary.status_code = 429
    mock_response_primary.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Too Many Requests", request=AsyncMock(), response=mock_response_primary
    )
    
    mock_response_fallback = AsyncMock(spec=httpx.Response)
    mock_response_fallback.status_code = 200
    mock_response_fallback.aiter_lines = AsyncMock()
    
    # Feed side effects cleanly to simulate sequentially triggered connections
    mock_send.side_effect = [mock_response_primary, mock_response_fallback]
    
    router = ResilientStreamRouter()
    
    test_payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": True
    }
    
    response = await router.route_chat(test_payload)
    
    assert response.status_code == 200
    assert mock_send.call_count == 2
    await router.close()
