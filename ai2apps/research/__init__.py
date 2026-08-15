"""First-party web research Tools and the built-in Research Agent."""

from .agent import install_research_agent
from .provider import (
    BingWebProvider,
    SafeHttpClient,
    WebProvider,
    WebProviderError,
)
from .service import install_web_research_service

__all__ = [
    "BingWebProvider",
    "SafeHttpClient",
    "WebProvider",
    "WebProviderError",
    "install_research_agent",
    "install_web_research_service",
]
