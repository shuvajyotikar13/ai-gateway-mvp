import logging
import httpx
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
from app.config import settings
from app.gateway.translator import PayloadTranslator

logger = logging.getLogger("gateway.router")

class ResilientStreamRouter:
    """
    Orchestrates connection requests to primary downstream foundation models.
    Intercepts and handles HTTP transport anomalies, 429 Rate Limits, and 5xx errors 
    BEFORE yielding headers to downstream consumers to enable transparent fallbacks.
    """
    def __init__(self):
        # Dedicated async connection pooling engine
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=5.0, read=55.0),
            limits=httpx.Limits(max_connections=1000, max_keepalive_connections=200)
        )

    async def close(self):
        await self.client.aclose()

    async def route_chat(self, payload: Dict[str, Any]) -> StreamingResponse:
        # TODO: Add Semantic Caching verification step here before initiating upstream dispatch logic
        try:
            logger.info(f"Routing transaction block to target: {settings.PRIMARY_PROVIDER}")
            return await self._execute_primary_path(payload)
            
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            status_code = exc.response.status_code if hasattr(exc, 'response') else 500
            if status_code == 429 or status_code >= 500:
                logger.error(f"Primary cluster degradation detected (Status {status_code}). Engaging fallback route.")
                return await self._execute_fallback_path(payload)
            raise exc

    async def _execute_primary_path(self, payload: Dict[str, Any]) -> StreamingResponse:
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Build out streaming context execution manually to catch status codes early
        request = self.client.build_request(
            "POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
        )
        response = await self.client.send(request, stream=True)
        
        # Trigger an early raise if an error occurs to drop straight to the fallback logic
        response.raise_for_status()

        return StreamingResponse(
            self._openai_stream_generator(response), 
            media_type="text/event-stream"
        )

    async def _execute_fallback_path(self, payload: Dict[str, Any]) -> StreamingResponse:
        logger.info(f"Invoking active mutation translation schema targeting: {settings.SECONDARY_PROVIDER}")
        anthropic_payload = PayloadTranslator.openai_to_anthropic(payload)
        
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        request = self.client.build_request(
            "POST", "https://api.anthropic.com/v1/messages", json=anthropic_payload, headers=headers
        )
        response = await self.client.send(request, stream=True)
        response.raise_for_status()

        return StreamingResponse(
            self._anthropic_fallback_stream_generator(response), 
            media_type="text/event-stream"
        )

    async def _openai_stream_generator(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        try:
            async for chunk in response.aiter_lines():
                if chunk:
                    yield f"{chunk}\n\n"
        except Exception as exc:
            logger.error(f"Upstream trace disconnected mid-flight: {str(exc)}")
        finally:
            await response.aclose()

    async def _anthropic_fallback_stream_generator(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        try:
            async for chunk in response.aiter_lines():
                if chunk:
                    # Translate Anthropic stream outputs back to an OpenAI-compatible format
                    translated_chunk = PayloadTranslator.translate_anthropic_stream_chunk(chunk)
                    if translated_chunk:
                        yield translated_chunk
        except Exception as exc:
            logger.error(f"Secondary fallback pipe hit an exception: {str(exc)}")
        finally:
            await response.aclose()
