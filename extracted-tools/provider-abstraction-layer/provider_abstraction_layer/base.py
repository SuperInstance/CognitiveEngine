"""
Base provider interface for all API providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional
import time
import uuid
from datetime import datetime, timezone

from ..models import (
    GenerationRequest,
    GenerationResponse,
    ProviderConfig,
    ProviderType,
    ChatMessage
)
from ..utils.logger import get_logger, log_request_start, log_request_complete, log_request_error

logger = get_logger("provider")


class BaseProvider(ABC):
    """Base class for all API providers"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.provider_type = config.provider
        self.model_name = config.model_name

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion"""
        pass

    @abstractmethod
    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate text completion with streaming"""
        pass

    @abstractmethod
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        pass

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request data for API call"""
        raise NotImplementedError

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API response data"""
        raise NotImplementedError

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text (approximate)"""
        # Rough estimation: 1 token ≈ 4 characters for English
        return len(text) // 4

    def _count_messages_tokens(self, messages: list[ChatMessage]) -> int:
        """Count tokens in message list"""
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4

    async def _make_request_with_tracking(
        self,
        request: GenerationRequest,
        api_call: callable
    ) -> GenerationResponse:
        """Make API request with comprehensive tracking"""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Start logging
        log_request_start(
            request_id=request_id,
            provider=self.provider_type.value,
            model=self.model_name,
            input_messages=len(request.messages),
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        try:
            # Make the API call
            response_data, response_time_ms = await api_call()

            # Extract token counts
            input_tokens = self._extract_input_tokens(request, response_data)
            output_tokens = self._extract_output_tokens(response_data)
            content = self._extract_content(response_data)

            # Calculate cost
            cost = self.calculate_cost(input_tokens, output_tokens)

            # Create response
            response = GenerationResponse(
                request_id=request_id,
                content=content,
                provider_used=self.provider_type,
                model_used=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                processing_time_ms=response_time_ms,
                metadata={
                    "request": {
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                        "top_p": request.top_p
                    },
                    "response": response_data.get("usage", {})
                }
            )

            # Log completion
            log_request_complete(
                request_id=request_id,
                provider=self.provider_type.value,
                model=self.model_name,
                duration_ms=response_time_ms,
                tokens=input_tokens + output_tokens,
                cost=cost
            )

            return response

        except Exception as e:
            # Log error
            log_request_error(
                request_id=request_id,
                provider=self.provider_type.value,
                error=str(e)
            )

            # Re-raise with context
            raise Exception(f"{self.provider_type.value} API error: {str(e)}") from e

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from response"""
        # Try to get from response usage data
        if "usage" in response_data and "prompt_tokens" in response_data["usage"]:
            return response_data["usage"]["prompt_tokens"]

        # Fallback to estimation
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from response"""
        # Try to get from response usage data
        if "usage" in response_data and "completion_tokens" in response_data["usage"]:
            return response_data["usage"]["completion_tokens"]

        # Fallback: count tokens in generated content
        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        """Extract generated content from response"""
        raise NotImplementedError

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the provider"""
        raise NotImplementedError

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limit information"""
        return {
            "provider": self.provider_type.value,
            "model": self.model_name,
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries
        }

    def validate_request(self, request: GenerationRequest) -> None:
        """Validate request before processing"""
        if not request.messages:
            raise ValueError("Messages cannot be empty")

        # Check token limit
        estimated_tokens = self._count_messages_tokens(request.messages)
        if request.max_tokens and (estimated_tokens + request.max_tokens) > self.config.max_tokens:
            raise ValueError(f"Token limit exceeded: {estimated_tokens + request.max_tokens} > {self.config.max_tokens}")

        # Validate temperature
        if not 0 <= request.temperature <= 2:
            raise ValueError("Temperature must be between 0 and 2")

        # Validate top_p
        if not 0 <= request.top_p <= 1:
            raise ValueError("Top_p must be between 0 and 1")

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """Check if provider supports function calling"""
        return False

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            "provider": self.provider_type.value,
            "model": self.model_name,
            "base_url": self.config.base_url,
            "max_tokens": self.config.max_tokens,
            "cost_per_1m_input_tokens": self.config.cost_per_1m_input_tokens,
            "cost_per_1m_output_tokens": self.config.cost_per_1m_output_tokens,
            "supports_streaming": self.supports_streaming(),
            "supports_function_calling": self.supports_function_calling(),
            "is_active": self.config.is_active
        }