"""
Unit tests for BaseProvider
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ProviderType, ChatMessage, GenerationRequest, GenerationResponse, ProviderConfig
from base import BaseProvider


class MockProvider(BaseProvider):
    """Mock implementation of BaseProvider for testing"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.generate_call_count = 0
        self.stream_call_count = 0

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Mock generate implementation"""
        self.generate_call_count += 1
        return GenerationResponse(
            request_id="test-req-id",
            content="Mock response",
            provider_used=self.provider_type,
            model_used=self.model_name,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            processing_time_ms=100
        )

    async def generate_stream(self, request: GenerationRequest):
        """Mock generate_stream implementation"""
        self.stream_call_count += 1
        chunks = ["Mock", " ", "response"]
        for chunk in chunks:
            yield chunk

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Mock cost calculation"""
        return (input_tokens * self.config.cost_per_1m_input_tokens / 1_000_000 +
                output_tokens * self.config.cost_per_1m_output_tokens / 1_000_000)

    def _prepare_request_data(self, request: GenerationRequest):
        """Mock request data preparation"""
        return {"messages": [msg.dict() for msg in request.messages]}

    def _parse_response(self, response_data):
        """Mock response parsing"""
        return response_data

    def _extract_content(self, response_data):
        """Mock content extraction"""
        return response_data.get("content", "")


class TestBaseProvider:
    """Test BaseProvider functionality"""

    @pytest.fixture
    def mock_provider(self, sample_provider_config):
        """Create mock provider instance"""
        return MockProvider(sample_provider_config)

    @pytest.fixture
    def sample_request(self):
        """Create sample request"""
        return GenerationRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello")
            ],
            temperature=0.7,
            max_tokens=100
        )

    def test_provider_initialization(self, mock_provider):
        """Test provider initialization"""
        assert mock_provider.provider_type == ProviderType.CLAUDE
        assert mock_provider.model_name == "claude-3-5-haiku-20241022"
        assert mock_provider.config.provider == ProviderType.CLAUDE

    def test_count_tokens(self, mock_provider):
        """Test token counting (approximate)"""
        text = "Hello world! This is a test."
        # Rough estimation: 1 token ≈ 4 characters
        expected_tokens = len(text) // 4
        assert mock_provider._count_tokens(text) == expected_tokens

    def test_count_tokens_empty_string(self, mock_provider):
        """Test token counting with empty string"""
        assert mock_provider._count_tokens("") == 0

    def test_count_messages_tokens(self, mock_provider):
        """Test counting tokens in message list"""
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello world")
        ]
        total_chars = sum(len(msg.content) for msg in messages)
        expected_tokens = total_chars // 4
        assert mock_provider._count_messages_tokens(messages) == expected_tokens

    def test_calculate_cost(self, mock_provider):
        """Test cost calculation"""
        input_tokens = 1000
        output_tokens = 500

        # Cost = (1000 * 0.25 / 1M) + (500 * 1.25 / 1M)
        # = 0.00025 + 0.000625 = 0.000875
        expected_cost = (input_tokens * 0.25 / 1_000_000 +
                        output_tokens * 1.25 / 1_000_000)

        cost = mock_provider.calculate_cost(input_tokens, output_tokens)
        assert abs(cost - expected_cost) < 0.000001

    def test_extract_input_tokens_from_response(self, mock_provider, sample_request):
        """Test extracting input tokens from API response"""
        response_data = {
            "usage": {
                "prompt_tokens": 50
            }
        }
        tokens = mock_provider._extract_input_tokens(sample_request, response_data)
        assert tokens == 50

    def test_extract_input_tokens_fallback(self, mock_provider, sample_request):
        """Test input token extraction fallback to estimation"""
        response_data = {}  # No usage data
        tokens = mock_provider._extract_input_tokens(sample_request, response_data)
        # Should fall back to estimation
        assert tokens > 0

    def test_extract_output_tokens_from_response(self, mock_provider):
        """Test extracting output tokens from API response"""
        response_data = {
            "usage": {
                "completion_tokens": 30
            }
        }
        tokens = mock_provider._extract_output_tokens(response_data)
        assert tokens == 30

    def test_extract_output_tokens_fallback(self, mock_provider):
        """Test output token extraction fallback"""
        response_data = {
            "content": "This is a test response"
        }
        tokens = mock_provider._extract_output_tokens(response_data)
        # Should estimate from content length
        assert tokens > 0

    def test_validate_request_valid(self, mock_provider, sample_request):
        """Test validation of valid request"""
        # Should not raise exception
        mock_provider.validate_request(sample_request)

    def test_validate_request_empty_messages(self, mock_provider):
        """Test validation fails with empty messages"""
        request = GenerationRequest(messages=[])
        with pytest.raises(ValueError) as exc_info:
            mock_provider.validate_request(request)
        assert "Messages cannot be empty" in str(exc_info.value)

    def test_validate_request_token_limit_exceeded(self, mock_provider):
        """Test validation fails when token limit exceeded"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="A" * 10000)],
            max_tokens=100000  # Would exceed limit
        )
        with pytest.raises(ValueError) as exc_info:
            mock_provider.validate_request(request)
        assert "Token limit exceeded" in str(exc_info.value)

    def test_validate_request_temperature_too_high(self, mock_provider, sample_request):
        """Test validation fails with invalid temperature"""
        sample_request.temperature = 2.5
        with pytest.raises(ValueError) as exc_info:
            mock_provider.validate_request(sample_request)
        assert "Temperature must be between 0 and 2" in str(exc_info.value)

    def test_validate_request_temperature_too_low(self, mock_provider, sample_request):
        """Test validation fails with negative temperature"""
        sample_request.temperature = -0.1
        with pytest.raises(ValueError) as exc_info:
            mock_provider.validate_request(sample_request)
        assert "Temperature must be between 0 and 2" in str(exc_info.value)

    def test_validate_request_top_p_invalid(self, mock_provider, sample_request):
        """Test validation fails with invalid top_p"""
        sample_request.top_p = 1.5
        with pytest.raises(ValueError) as exc_info:
            mock_provider.validate_request(sample_request)
        assert "Top_p must be between 0 and 1" in str(exc_info.value)

    def test_validate_request_top_p_boundary(self, mock_provider, sample_request):
        """Test validation with boundary top_p values"""
        sample_request.top_p = 0.0
        mock_provider.validate_request(sample_request)

        sample_request.top_p = 1.0
        mock_provider.validate_request(sample_request)

    @pytest.mark.asyncio
    async def test_generate_with_tracking(self, mock_provider, sample_request):
        """Test generate with request tracking"""
        response = await mock_provider.generate(sample_request)

        assert response.content == "Mock response"
        assert response.provider_used == ProviderType.CLAUDE
        assert response.model_used == "claude-3-5-haiku-20241022"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.cost_usd == 0.001
        assert response.processing_time_ms == 100
        assert mock_provider.generate_call_count == 1

    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_provider, sample_request):
        """Test streaming generation"""
        chunks = []
        async for chunk in mock_provider.generate_stream(sample_request):
            chunks.append(chunk)

        assert chunks == ["Mock", " ", "response"]
        assert mock_provider.stream_call_count == 1

    def test_supports_streaming(self, mock_provider):
        """Test streaming support check"""
        assert mock_provider.supports_streaming() is True

    def test_supports_function_calling(self, mock_provider):
        """Test function calling support check"""
        assert mock_provider.supports_function_calling() is False

    def test_get_rate_limit_info(self, mock_provider):
        """Test getting rate limit information"""
        info = mock_provider.get_rate_limit_info()
        assert info["provider"] == "claude"
        assert info["model"] == "claude-3-5-haiku-20241022"
        assert info["rate_limit_per_minute"] == 50
        assert info["timeout"] == 30
        assert info["max_retries"] == 3

    def test_get_provider_info(self, mock_provider):
        """Test getting provider information"""
        info = mock_provider.get_provider_info()
        assert info["provider"] == "claude"
        assert info["model"] == "claude-3-5-haiku-20241022"
        assert info["base_url"] == "https://api.anthropic.com"
        assert info["max_tokens"] == 8192
        assert info["cost_per_1m_input_tokens"] == 0.25
        assert info["cost_per_1m_output_tokens"] == 1.25
        assert info["supports_streaming"] is True
        assert info["supports_function_calling"] is False
        assert info["is_active"] is True

    @pytest.mark.asyncio
    async def test_health_check_not_implemented(self, mock_provider):
        """Test that health check raises NotImplementedError"""
        with pytest.raises(NotImplementedError):
            await mock_provider.health_check()

    def test_prepare_request_data_not_implemented(self, mock_provider, sample_request):
        """Test that _prepare_request_data raises NotImplementedError in base"""
        # Our mock overrides it, so test with base class
        base_provider = BaseProvider(mock_provider.config)
        with pytest.raises(NotImplementedError):
            base_provider._prepare_request_data(sample_request)

    def test_parse_response_not_implemented(self, mock_provider):
        """Test that _parse_response raises NotImplementedError in base"""
        base_provider = BaseProvider(mock_provider.config)
        with pytest.raises(NotImplementedError):
            base_provider._parse_response({})

    def test_extract_content_not_implemented(self, mock_provider):
        """Test that _extract_content raises NotImplementedError in base"""
        base_provider = BaseProvider(mock_provider.config)
        with pytest.raises(NotImplementedError):
            base_provider._extract_content({})


class TestTokenCountingEdgeCases:
    """Test edge cases in token counting"""

    @pytest.fixture
    def mock_provider(self, sample_provider_config):
        """Create mock provider"""
        return MockProvider(sample_provider_config)

    def test_count_very_long_text(self, mock_provider):
        """Test counting tokens in very long text"""
        text = "A" * 10000
        tokens = mock_provider._count_tokens(text)
        assert tokens == 2500  # 10000 // 4

    def test_count_unicode_characters(self, mock_provider):
        """Test counting tokens with unicode characters"""
        text = "Hello 世界 🌍"
        # Should still work, though estimation may be less accurate
        tokens = mock_provider._count_tokens(text)
        assert tokens >= 0

    def test_count_special_characters(self, mock_provider):
        """Test counting tokens with special characters"""
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        tokens = mock_provider._count_tokens(text)
        assert tokens >= 0
