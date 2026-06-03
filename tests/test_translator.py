import pytest
import json
from app.gateway.translator import PayloadTranslator

def test_openai_to_anthropic_payload_mapping():
    openai_payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are an expert platform architect."},
            {"role": "user", "content": "Explain shared-nothing architecture."}
        ],
        "temperature": 0.7,
        "stream": True
    }
    
    translated = PayloadTranslator.openai_to_anthropic(openai_payload)
    
    assert translated["model"] == "claude-3-5-sonnet-20240620"
    assert translated["system"] == "You are an expert platform architect."
    assert len(translated["messages"]) == 1
    assert translated["messages"][0]["role"] == "user"
    assert translated["messages"][0]["content"] == "Explain shared-nothing architecture."
    assert translated["stream"] is True
    assert translated["temperature"] == 0.7

def test_anthropic_stream_chunk_translation():
    anthropic_raw_line = 'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Concurrency"}}'
    
    translated_line = PayloadTranslator.translate_anthropic_stream_chunk(anthropic_raw_line)
    
    assert translated_line.startswith("data: ")
    json_data = json.loads(translated_line.replace("data: ", "").strip())
    assert json_data["choices"][0]["delta"]["content"] == "Concurrency"
