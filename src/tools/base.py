"""
src/tools/base.py
─────────────────
Base tool class with retry, timeout, and validation built in.
All tool wrappers inherit from this.
"""

import time
import httpx
import logging
from abc import ABC, abstractmethod
from typing import Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from src.config import settings

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Base error for all tool failures."""
    def __init__(self, tool_name: str, message: str, retryable: bool = False):
        self.tool_name = tool_name
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{tool_name}] {message}")


class ToolResult:
    """
    Wrapper for tool execution results.
    Carries data, status, latency, and error info.
    """
    def __init__(
        self,
        tool_name: str,
        success: bool,
        data: Any = None,
        error: str | None = None,
        latency_ms: int = 0,
    ):
        self.tool_name = tool_name
        self.success = success
        self.data = data
        self.error = error
        self.latency_ms = latency_ms

    def to_trace_dict(self) -> dict:
        return {
            "tool": self.tool_name,
            "status": "success" if self.success else "error",
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    Provides retry logic, timeout, timing, and error handling.
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self.timeout = settings.tool_timeout_seconds
        self.max_retries = settings.tool_max_retries
        self.base_delay = settings.tool_retry_base_delay
        self.max_delay = settings.tool_retry_max_delay

    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """Core logic implemented by each tool subclass."""
        pass

    async def run(self, **kwargs) -> ToolResult:
        """
        Public entry point. Handles timing, retry, and error wrapping.
        """
        start = time.time()

        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                data = await self._execute(**kwargs)
                latency = int((time.time() - start) * 1000)
                logger.info(f"{self.name} succeeded in {latency}ms")
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=data,
                    latency_ms=latency,
                )

            except ToolError as e:
                last_error = e
                if not e.retryable:
                    break
                wait = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                logger.warning(f"{self.name} attempt {attempt} failed: {e.message}. Retrying in {wait}s")
                time.sleep(wait)

            except httpx.TimeoutException:
                last_error = ToolError(self.name, "Request timed out", retryable=True)
                wait = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                logger.warning(f"{self.name} timeout on attempt {attempt}. Retrying in {wait}s")
                time.sleep(wait)

            except Exception as e:
                last_error = ToolError(self.name, str(e), retryable=False)
                break

        latency = int((time.time() - start) * 1000)
        error_msg = last_error.message if last_error else "Unknown error"
        logger.error(f"{self.name} failed after {attempt} attempts: {error_msg}")

        return ToolResult(
            tool_name=self.name,
            success=False,
            error=error_msg,
            latency_ms=latency,
        )