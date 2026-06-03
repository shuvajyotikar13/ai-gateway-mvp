# ai-gateway-mvp
production-grade directory structure for a Python-based MVP. for speed of development and native async/streaming support

# Minimalist AI Gateway MVP

A high-performance, resilient AI Gateway prototype built in Go, engineered to handle intelligent model routing, seamless fallbacks, and multi-tenant rate limiting. This architecture uses **Dragonfly** as a highly concurrent, multi-threaded caching and rate-limiting backbone.

## System Architecture

[ Client Application ]
│  (OpenAI-Compatible JSON / SSE Stream)
▼
[ AI Gateway Data Plane ] ──────► [ Dragonfly Cache / Rate Limiter ]
│
├───► Try: OpenAI API (Primary)
│      │
│      └─► (If 429 / 500)
│
└───► Fallback: Anthropic API (Secondary)

### Core Architectural Features

1. **Unified Interface:** Exposes an OpenAI-compliant `/v1/chat/completions` endpoint.
2. **Dynamic Payload Translation:** On-the-fly request/response mutation between divergent upstream schemas (OpenAI $\Leftrightarrow$ Anthropic).
3. **Resilient Stream-Switching:** Catches upstream failures at initiation and instantly shifts traffic without breaking the client-facing SSE connection.
4. **Multi-Threaded Rate Limiting:** High-throughput token-bucket tracking leveraging Dragonfly's shared-nothing memory architecture.

---

## Getting Started

### Prerequisites

* Go 1.22+
* Docker and Docker Compose

### Environment Configuration

Create a `.env` file in the root directory:

```env
PORT=8080
DRAGONFLY_URL=redis://localhost:6379/0

OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Routing Policy: primary | fallback
PRIMARY_PROVIDER=openai
SECONDARY_PROVIDER=anthropic
```

### Local Deployment

1. Spin up Dragonfly and Infrastructure:

```bash
docker-compose up -d
```

2. Install project dependencies locally:

``` bash
pip install -r requirements.txt
```

3. Execute validation integration testing targets:

```bash
pytest -v
```

4. Launch the Gateway control loop interface:

```bash
uvicorn app.main:app --port 8080 --reload
```

5. Verify the Streaming Ingress:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "stream": true,
    "messages": [{"role": "user", "content": "Explain distributed consensus."}]
  }'
```
---

## Engineering Deep Dives & Trade-offs

### The Fallback State-Machine
Handling errors in standard HTTP requests is trivial; handling them in streaming payloads is highly complex. The gateway reads the first byte of the response from the primary provider. If an immediate failure occurs, it re-routes the buffer payload to the translator pipeline for the fallback provider before flushing the HTTP 200 OK status header to the client.

### Distributed Token Verification
Instead of standard request-based limiting, this gateway relies on a dual-token bucket framework mapping both total operations and estimated volumetric context window tokens concurrently. Dragonfly enables ultra-low latency execution of these atomic validation blocks even under severe client connection concurrency.
