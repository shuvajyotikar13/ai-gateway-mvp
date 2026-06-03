from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger("gateway.translator")

class PayloadTranslator:
    """
    Handles bidirectional schema mutation between supported model providers.
    Ensures structural integrity across divergent API interfaces.
    """

    @staticmethod
    def openai_to_anthropic(openai_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates an OpenAI Chat Completions payload into an Anthropic Messages payload.
        """
        openai_messages: List[Dict[str, Any]] = openai_body.get("messages", [])
        anthropic_messages: List[Dict[str, Any]] = []
        system_prompt: str = ""

        for msg in openai_messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role == "system":
                system_prompt = content
            elif role in ["user", "assistant"]:
                anthropic_messages.append({"role": role, "content": content})
            else:
                # FIXME: Handle tool/function call roles or map gracefully
                logger.warning(f"Unsupported message role detected during translation: {role}")

        # Extract parameters and provide reliable fallbacks
        temperature = openai_body.get("temperature", 1.0)
        # Anthropic bounds temperature between 0.0 and 1.0
        anthropic_temp = max(0.0, min(temperature, 1.0))

        anthropic_body = {
            "model": "claude-3-5-sonnet-20240620",
            "messages": anthropic_messages,
            "max_tokens": openai_body.get("max_tokens", 4096),
            "stream": openai_body.get("stream", False),
            "temperature": anthropic_temp
        }
        
        if system_prompt:
            anthropic_body["system"] = system_prompt

        return anthropic_body

    @staticmethod
    def translate_anthropic_stream_chunk(anthropic_line: str) -> str:
        """
        Translates a single line chunk from Anthropic stream syntax into OpenAI data format.
        Allows frontend applications to consume responses uninterrupted.
        """
        if not anthropic_line.startswith("data:"):
            return ""
        
        raw_data = anthropic_line.replace("data:", "").strip()
        if not raw_data or raw_data == "[DONE]":
            return "data: [DONE]\n\n"

        try:
            event = json.loads(raw_data)
            event_type = event.get("type")
            
            # Translate content block deltas smoothly
            if event_type == "content_block_delta":
                delta_text = event.get("delta", {}).get("text", "")
                openai_chunk = {
                    "choices": [{
                        "delta": {"content": delta_text},
                        "finish_reason": None,
                        "index": 0
                    }]
                }
                return f"data: {json.dumps(openai_chunk)}\n\n"
                
            elif event_type == "message_delta":
                # Signal stream terminal states gracefully
                finish_reason = event.get("delta", {}).get("stop_reason", "stop")
                openai_chunk = {
                    "choices": [{
                        "delta": {},
                        "finish_reason": finish_reason,
                        "index": 0
                    }]
                }
                return f"data: {json.dumps(openai_chunk)}\n\n"
                
        except json.JSONDecodeError:
            logger.error("Failed to parse Anthropic stream chunk schema")
            
        return ""
