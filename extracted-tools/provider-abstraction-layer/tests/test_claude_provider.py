"""
Unit tests for ClaudeProvider
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ProviderType, ChatMessage, GenerationRequest, ProviderConfig
from providers.claude_provider import ClaudeProvider


class TestClaudeProvider:
    """Test ClaudeProvider implementation"""

    @pytest.fixture
    def claude_provider(self, sample_provider_config):
        """Create Claude provider instance"""
        return ClaudeProvider(sample_provider_config)

    @pytest.fixture
    def sample_request(self):
        """Create sample generation request"""
        return GenerationRequest(
            messages=[
                ChatMessage(role="system", content="You are a helpful assistant."),
                ChatMessage(role="user", content="Hello, how are you?")
            ],
            temperature=0.7,
            max_tokens=1000,
            top_p=0.9
        )

    def test_provider_initialization(self, claude_provider):
        """Test Claude provider initialization"""
        assert claude_provider.provider_type == ProviderType.CLAUDE
        assert claude_provider.model_name == "claude-3-5-haiku-20241022"
        assert claude_provider.api_key == "test-api-key"
        assert claude_provider.base_url == "https://api.anthropic.com"
        assert claude_provider.timeout == 30
        assert claude_provider.anthropic_version == "2023-06-01"

    def test_prepare_request_data_with_system_message(self, claude_provider, sample_request):
        """Test preparing request data with system message"""
        request_data = claude_provider._prepare_request_data(sample_request)

        assert request_data["model"] == "claude-3-5-haiku-20241022"
        assert request_data["max_tokens"] == 1000
        assert request_data["temperature"] == 0.7
        assert request_data["top_p"] == 0.9
        assert "system" in request_data
        assert request_data["system"] == "You are a helpful assistant."
        assert len(request_data["messages"]) == 1
        assert request_data["messages"][0]["role"] == "user"

    def test_prepare_request_data_without_system_message(self, claude_provider):
        """Test preparing request data without system message"""
        request = GenerationRequest(
            messages=[
                ChatMessage(role="user", content="Hello")
            ]
        )
        request_data = claude_provider._prepare_request_data(request)

        assert "system" not in request_data
        assert len(request_data["messages"]) == 1

    def test_prepare_request_data_default_max_tokens(self, claude_provider):
        """Test preparing request data with default max_tokens"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            max_tokens=None
        )
        request_data = claude_provider._prepare_request_data(request)

        assert request_data["max_tokens"] == 4096  # Default

    def test_get_headers(self, claude_provider):
        """Test getting request headers"""
        headers = claude_provider._get_headers()

        assert headers["x-api-key"] == "test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["User-Agent"] == "LucidDreamer-Router/1.0"

    def test_parse_response_valid(self, claude_provider):
        """Test parsing valid Claude response"""
        response_data = {
            "type": "message",
            "content": [
                {
                    "type": "text",
                    "text": "Hello! I'm doing well."
                }
            ],
            "usage": {
                "input_tokens": 20,
                "output_tokens": 10
            },
            "model": "claude-3-5-haiku-20241022",
            "id": "msg-123",
            "stop_reason": "end_turn"
        }

        parsed = claude_provider._parse_response(response_data)

        assert parsed["content"] == "Hello! I'm doing well."
        assert parsed["usage"]["input_tokens"] == 20
        assert parsed["usage"]["output_tokens"] == 10
        assert parsed["stop_reason"] == "end_turn"
        assert parsed["model"] == "claude-3-5-haiku-20241022"

    def test_parse_response_invalid_type(self, claude_provider):
        """Test parsing response with invalid type"""
        response_data = {
            "type": "error",
            "content": []
        }

        with pytest.raises(ValueError) as exc_info:
            claude_provider._parse_response(response_data)
        assert "Invalid response format" in str(exc_info.value)

    def test_parse_response_multiple_text_blocks(self, claude_provider):
        """Test parsing response with multiple text blocks"""
        response_data = {
            "type": "message",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": " world"},
                {"type": "text", "text": "!"}
            ]
        }

        parsed = claude_provider._parse_response(response_data)
        assert parsed["content"] == "Hello world!"

    def test_extract_content(self, claude_provider):
        """Test extracting content from response"""
        response_data = {
            "content": [
                {"type": "text", "text": "Test content"}
            ]
        }

        content = claude_provider._extract_content(response_data)
        assert content == "Test content"

    def test_extract_content_empty(self, claude_provider):
        """Test extracting content from empty response"""
        response_data = {"content": []}
        content = claude_provider._extract_content(response_data)
        assert content == ""

    def test_extract_input_tokens_from_response(self, claude_provider, sample_request):
        """Test extracting input tokens from Claude response"""
        response_data = {
            "usage": {
                "input_tokens": 25
            }
        }

        tokens = claude_provider._extract_input_tokens(sample_request, response_data)
        assert tokens == 25

    def test_extract_input_tokens_fallback(self, claude_provider, sample_request):
        """Test input token extraction fallback"""
        response_data = {}
        tokens = claude_provider._extract_input_tokens(sample_request, response_data)
        # Should estimate from messages
        assert tokens > 0

    def test_extract_output_tokens_from_response(self, claude_provider):
        """Test extracting output tokens from Claude response"""
        response_data = {
            "usage": {
                "output_tokens": 15
            }
        }

        tokens = claude_provider._extract_output_tokens(response_data)
        assert tokens == 15

    def test_extract_output_tokens_fallback(self, claude_provider):
        """Test output token extraction fallback"""
        response_data = {
            "content": "This is a test response"
        }
        tokens = claude_provider._extract_output_tokens(response_data)
        # Should estimate from content
        assert tokens > 0

    def test_calculate_cost(self, claude_provider):
        """Test cost calculation for Claude"""
        input_tokens = 1000
        output_tokens = 500

        # Cost = (1000 * 0.25 / 1M) + (500 * 1.25 / 1M)
        # = 0.00025 + 0.000625 = 0.000875
        cost = claude_provider.calculate_cost(input_tokens, output_tokens)

        expected = (input_tokens * 0.25 / 1_000_000 +
                   output_tokens * 1.25 / 1_000_000)
        assert abs(cost - expected) < 0.000001

    def test_supports_streaming(self, claude_provider):
        """Test that Claude supports streaming"""
        assert claude_provider.supports_streaming() is True

    def test_supports_function_calling(self, claude_provider):
        """Test that Claude supports function calling"""
        assert claude_provider.supports_function_calling() is True

    @pytest.mark.asyncio
    async def test_generate_success(self, claude_provider, sample_request, mock_httpx_client):
        """Test successful generation"""
        with patch('httpx.AsyncClient', return_value=mock_httpx_client):
            response = await claude_provider.generate(sample_request)

            assert response.content == "Test response"
            assert response.provider_used == ProviderType.CLAUDE
            assert response.input_tokens == 20
            assert response.output_tokens == 15
            assert response.cost_usd > 0

    @pytest.mark.asyncio
    async def test_generate_stream(self, claude_provider, sample_request):
        """Test streaming generation"""
        mock_stream_response = AsyncMock()
        mock_stream_response.raise_for_status = Mock()

        # Mock streaming lines
        async def mock_aiter_lines():
            lines = [
                'data: {"type": "content_block_delta", "delta": {"text": "Hello"}}',
                'data: {"type": "content_block_delta", "delta": {"text": " world"}}',
                'data: {"type": "content_block_delta", "delta": {"text": "!"}}',
                'data: [DONE]'
            ]
            for line in lines:
                yield line

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_stream_response
        mock_stream_context.__aenter__.return_value.aiter_lines = mock_aiter_lines
        mock_stream_context.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = Mock(return_value=mock_stream_context)

        with patch('httpx.AsyncClient', return_value=mock_client):
            chunks = []
            async for chunk in claude_provider.generate_stream(sample_request):
                chunks.append(chunk)

            assert chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_generate_stream_json_error(self, claude_provider, sample_request):
        """Test streaming with JSON decode errors"""
        async def mock_aiter_lines():
            lines = [
                'data: invalid json',
                'data: {"type": "content_block_delta", "delta": {"text": "Hello"}}',
                'data: [DONE]'
            ]
            for line in lines:
                yield line

        mock_stream_response = AsyncMock()
        mock_stream_response.raise_for_status = Mock()
        mock_stream_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_stream_response
        mock_stream_context.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = Mock(return_value=mock_stream_context)

        with patch('httpx.AsyncClient', return_value=mock_client):
            chunks = []
            async for chunk in claude_provider.generate_stream(sample_request):
                chunks.append(chunk)

            # Should skip invalid JSON and continue
            assert chunks == ["Hello"]

    def test_estimate_request_cost(self, claude_provider, sample_request):
        """Test estimating request cost before making it"""
        cost = claude_provider.estimate_request_cost(sample_request)
        assert cost >= 0
        assert isinstance(cost, float)

    def test_is_cost_effective_for_conversational(self, claude_provider):
        """Test cost effectiveness for conversational content"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Let's have a conversation")]
        )
        assert claude_provider.is_cost_effective_for(request) is True

    def test_is_cost_effective_for_summarization(self, claude_provider):
        """Test cost effectiveness for summarization"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Please summarize this document")]
        )
        assert claude_provider.is_cost_effective_for(request) is True

    def test_is_cost_effective_for_analysis(self, claude_provider):
        """Test cost effectiveness for analysis"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Analyze this data")]
        )
        assert claude_provider.is_cost_effective_for(request) is True

    def test_is_cost_effective_for_short_content(self, claude_provider):
        """Test cost effectiveness for short content"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Hi")]
        )
        assert claude_provider.is_cost_effective_for(request) is True

    def test_get_quality_score(self, claude_provider):
        """Test getting quality score"""
        score = claude_provider.get_quality_score()
        assert score == 0.87
        assert 0 <= score <= 1

    def test_get_performance_characteristics(self, claude_provider):
        """Test getting performance characteristics"""
        characteristics = claude_provider.get_performance_characteristics()

        assert "average_response_time_ms" in characteristics
        assert "throughput_tokens_per_second" in characteristics
        assert "context_window" in characteristics
        assert "supported_languages" in characteristics
        assert "specialties" in characteristics
        assert "cost_tier" in characteristics
        assert "quality_tier" in characteristics
        assert "speed_tier" in characteristics
        assert "strengths" in characteristics

        assert characteristics["cost_tier"] == "low"
        assert characteristics["quality_tier"] == "high"
        assert characteristics["speed_tier"] == "very_fast"

    def test_get_optimal_temperature_range(self, claude_provider):
        """Test getting optimal temperature ranges"""
        ranges = claude_provider.get_optimal_temperature_range()

        assert "creative" in ranges
        assert "balanced" in ranges
        assert "precise" in ranges
        assert "analytical" in ranges

        assert 0 <= ranges["analytical"] <= 2

    def test_analyze_request_characteristics(self, claude_provider):
        """Test analyzing request characteristics"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Hello, let's chat")]
        )

        analysis = claude_provider.analyze_request_characteristics(request)

        assert "suitability_score" in analysis
        assert "characteristics" in analysis
        assert "recommended" in analysis
        assert "optimization_tips" in analysis

        assert 0 <= analysis["suitability_score"] <= 1
        assert isinstance(analysis["recommended"], bool)

    def test_get_rate_limits(self, claude_provider):
        """Test getting rate limits"""
        limits = claude_provider.get_rate_limits()

        assert "requests_per_minute" in limits
        assert "tokens_per_minute" in limits
        assert "max_concurrent_requests" in limits

        assert limits["requests_per_minute"] == 50
        assert limits["tokens_per_minute"] == 500_000
        assert limits["max_concurrent_requests"] == 10

    @pytest.mark.asyncio
    async def test_health_check_success(self, claude_provider):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usage": {
                "input_tokens": 5,
                "output_tokens": 3
            }
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch('httpx.AsyncClient', return_value=mock_client):
            health = await claude_provider.health_check()

            assert health["status"] == "healthy"
            assert health["response_time_ms"] >= 0
            assert health["model"] == "claude-3-5-haiku-20241022"

    @pytest.mark.asyncio
    async def test_health_check_failure(self, claude_provider):
        """Test health check with failure"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch('httpx.AsyncClient', return_value=mock_client):
            health = await claude_provider.health_check()

            assert health["status"] == "unhealthy"
            assert "error" in health

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, claude_provider):
        """Test health check with timeout"""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection timeout")

        with patch('httpx.AsyncClient', return_value=mock_client):
            health = await claude_provider.health_check()

            assert health["status"] == "unhealthy"
            assert "timeout" in health["error"].lower() or "connection" in health["error"].lower()
