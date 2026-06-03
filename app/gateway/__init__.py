"""
Gateway Module.

Exposes resilient streaming routers and real-time bidirectional schema translation engines
to normalize communication boundaries between divergent foundation model APIs.
"""

from app.gateway.router import ResilientStreamRouter
from app.gateway.translator import PayloadTranslator

# Define explicit public exports to prevent namespace pollution
__all__ = [
    "ResilientStreamRouter",
    "PayloadTranslator",
]
