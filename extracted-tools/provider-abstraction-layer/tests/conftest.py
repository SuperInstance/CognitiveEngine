"""
Pytest configuration and shared fixtures for provider-abstraction-layer tests
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    ProviderType,
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
    ProviderConfig,
    PriorityLevel
)


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_provider_config():
    """Sample provider configuration"""
    return ProviderConfig(
        provider=ProviderType.CLAUDE,
        model_name="claude-3-5-haiku-20241022",
        api_key="test-api-key",
        base_url="https://api.anthropic.com",
        cost_per_1m_input_tokens=0.25,
        cost_per_1m_output_tokens=1.25,
        max_tokens=8192,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=50,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def sample_openai_config():
    """Sample OpenAI provider configuration"""
    return ProviderConfig(
        provider=ProviderType.OPENAI,
        model_name="gpt-4o-mini",
        api_key="test-openai-key",
        base_url="https://api.openai.com/v1",
        cost_per_1m_input_tokens=0.15,
        cost_per_1m_output_tokens=0.60,
        max_tokens=128000,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=60
    )


@pytest.fixture
def sample_glm_config():
    """Sample GLM provider configuration"""
    return ProviderConfig(
        provider=ProviderType.GLM,
        model_name="glm-4-plus",
        api_key="test-glm-key",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        cost_per_1m_input_tokens=0.5,
        cost_per_1m_output_tokens=0.5,
        max_tokens=128000,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=60
    )


@pytest.fixture
def sample_messages():
    """Sample chat messages"""
    return [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello, how are you?")
    ]


@pytest.fixture
def sample_request(sample_messages):
    """Sample generation request"""
    return GenerationRequest(
        messages=sample_messages,
        max_tokens=1000,
        temperature=0.7,
        top_p=1.0,
        stream=False,
        user_id="test_user",
        session_id="test_session",
        priority=PriorityLevel.NORMAL,
        metadata={"test": "data"}
    )


@pytest.fixture
def sample_response():
    """Sample generation response"""
    return GenerationResponse(
        request_id="test-request-id",
        content="Hello! I'm doing well, thank you for asking!",
        provider_used=ProviderType.CLAUDE,
        model_used="claude-3-5-haiku-20241022",
        input_tokens=20,
        output_tokens=15,
        cost_usd=0.000023,
        processing_time_ms=650,
        cached=False,
        metadata={
            "temperature": 0.7,
            "max_tokens": 1000,
            "model": "claude-3-5-haiku-20241022"
        }
    )


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "type": "message",
        "content": [
            {
                "type": "text",
                "text": "Test response"
            }
        ],
        "usage": {
            "input_tokens": 20,
            "output_tokens": 15
        },
        "model": "claude-3-5-haiku-20241022",
        "id": "msg-123",
        "stop_reason": "end_turn"
    }
    mock_client.post.return_value = mock_response
    mock_client.stream.return_value.__aenter__.return_value.aiter_lines.return_value = [
        "data: {\"type\": \"content_block_delta\", \"delta\": {\"text\": \"Test\"}}",
        "data: [DONE]"
    ]
    return mock_client


@pytest.fixture
def mock_httpx_error_client():
    """Mock httpx.AsyncClient that returns errors"""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = Exception("HTTP 500: Internal Server Error")
    mock_client.post.return_value = mock_response
    return mock_client


@pytest.fixture
def claude_api_response_data():
    """Sample Claude API response data"""
    return {
        "type": "message",
        "content": [
            {
                "type": "text",
                "text": "Hello! I'm doing well, thank you for asking!"
            }
        ],
        "usage": {
            "input_tokens": 20,
            "output_tokens": 15
        },
        "model": "claude-3-5-haiku-20241022",
        "id": "msg-123",
        "stop_reason": "end_turn"
    }


@pytest.fixture
def openai_api_response_data():
    """Sample OpenAI API response data"""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! I'm doing well, thank you for asking!"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 15,
            "total_tokens": 35
        }
    }


@pytest.fixture
def timeout_fixture():
    """Timeout fixture for tests"""
    return 30


@pytest.fixture
def async_mock():
    """Create an async mock"""
    return AsyncMock()


@pytest.fixture
def sync_mock():
    """Create a sync mock"""
    return Mock()


@pytest.fixture
def sample_streaming_chunks():
    """Sample streaming response chunks"""
    return [
        "Hello",
        "! ",
        "I'm",
        " doing",
        " well",
        ", thank",
        " you",
        " for",
        " asking",
        "!"
    ]


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "async: Async tests")
