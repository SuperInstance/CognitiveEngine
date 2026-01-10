"""
Unit tests for data models
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    ProviderType,
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
    ProviderConfig,
    PriorityLevel,
    RoutingDecision,
    CostTracking,
    BudgetStatus,
    ProviderMetrics,
    HealthCheck,
    QueueItem,
    Alert,
    UsageAnalytics,
    PerformanceReport,
    APIResponse,
    StreamChunk
)


class TestProviderType:
    """Test ProviderType enum"""

    def test_provider_type_values(self):
        """Test provider type enum values"""
        assert ProviderType.GLM.value == "glm"
        assert ProviderType.DEEPSEEK.value == "deepseek"
        assert ProviderType.CLAUDE.value == "claude"
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.DEEPINFRA.value == "deepinfra"

    def test_provider_type_comparison(self):
        """Test provider type comparison"""
        assert ProviderType.CLAUDE == ProviderType.CLAUDE
        assert ProviderType.CLAUDE != ProviderType.OPENAI


class TestChatMessage:
    """Test ChatMessage model"""

    def test_create_chat_message(self):
        """Test creating a chat message"""
        message = ChatMessage(
            role="user",
            content="Hello, how are you?"
        )
        assert message.role == "user"
        assert message.content == "Hello, how are you?"
        assert message.name is None

    def test_create_chat_message_with_name(self):
        """Test creating a chat message with name"""
        message = ChatMessage(
            role="user",
            content="Hello",
            name="John"
        )
        assert message.name == "John"

    def test_chat_message_serialization(self):
        """Test chat message serialization"""
        message = ChatMessage(role="user", content="Test")
        data = message.dict()
        assert data["role"] == "user"
        assert data["content"] == "Test"


class TestGenerationRequest:
    """Test GenerationRequest model"""

    def test_create_minimal_request(self):
        """Test creating a minimal request"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert len(request.messages) == 1
        assert request.temperature == 0.7  # Default
        assert request.max_tokens is None
        assert request.stream is False

    def test_create_full_request(self):
        """Test creating a full request with all parameters"""
        request = GenerationRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello")
            ],
            max_tokens=1000,
            temperature=0.5,
            top_p=0.9,
            stream=True,
            user_id="user123",
            session_id="session456",
            priority=PriorityLevel.HIGH,
            preferred_provider=ProviderType.CLAUDE,
            metadata={"key": "value"}
        )
        assert len(request.messages) == 2
        assert request.max_tokens == 1000
        assert request.temperature == 0.5
        assert request.top_p == 0.9
        assert request.stream is True
        assert request.user_id == "user123"
        assert request.session_id == "session456"
        assert request.priority == PriorityLevel.HIGH
        assert request.preferred_provider == ProviderType.CLAUDE
        assert request.metadata == {"key": "value"}

    def test_request_validation_empty_messages(self):
        """Test that empty messages are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(messages=[])
        assert "Messages cannot be empty" in str(exc_info.value)

    def test_request_validation_temperature_too_high(self):
        """Test that temperature > 2 is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(
                messages=[ChatMessage(role="user", content="Test")],
                temperature=2.5
            )
        assert "Temperature must be between 0 and 2" in str(exc_info.value)

    def test_request_validation_temperature_negative(self):
        """Test that negative temperature is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(
                messages=[ChatMessage(role="user", content="Test")],
                temperature=-0.1
            )
        assert "Temperature must be between 0 and 2" in str(exc_info.value)

    def test_request_validation_temperature_boundary(self):
        """Test temperature boundary values"""
        # Should work
        request1 = GenerationRequest(
            messages=[ChatMessage(role="user", content="Test")],
            temperature=0
        )
        assert request1.temperature == 0

        request2 = GenerationRequest(
            messages=[ChatMessage(role="user", content="Test")],
            temperature=2
        )
        assert request2.temperature == 2


class TestGenerationResponse:
    """Test GenerationResponse model"""

    def test_create_response(self):
        """Test creating a generation response"""
        response = GenerationResponse(
            request_id="req-123",
            content="Hello, world!",
            provider_used=ProviderType.CLAUDE,
            model_used="claude-3-5-haiku",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            processing_time_ms=500
        )
        assert response.request_id == "req-123"
        assert response.content == "Hello, world!"
        assert response.provider_used == ProviderType.CLAUDE
        assert response.model_used == "claude-3-5-haiku"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.cost_usd == 0.0001
        assert response.processing_time_ms == 500
        assert response.cached is False  # Default
        assert response.metadata == {}  # Default

    def test_response_with_cache_and_metadata(self):
        """Test response with cache flag and metadata"""
        response = GenerationResponse(
            request_id="req-123",
            content="Test",
            provider_used=ProviderType.OPENAI,
            model_used="gpt-4",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0002,
            processing_time_ms=600,
            cached=True,
            metadata={"model": "gpt-4", "cached_at": "2024-01-01"}
        )
        assert response.cached is True
        assert response.metadata["cached_at"] == "2024-01-01"


class TestProviderConfig:
    """Test ProviderConfig model"""

    def test_create_config(self):
        """Test creating provider config"""
        config = ProviderConfig(
            provider=ProviderType.CLAUDE,
            model_name="claude-3-5-haiku",
            api_key="test-key",
            base_url="https://api.anthropic.com",
            cost_per_1m_input_tokens=0.25,
            cost_per_1m_output_tokens=1.25,
            max_tokens=8192
        )
        assert config.provider == ProviderType.CLAUDE
        assert config.model_name == "claude-3-5-haiku"
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.anthropic.com"
        assert config.cost_per_1m_input_tokens == 0.25
        assert config.cost_per_1m_output_tokens == 1.25
        assert config.max_tokens == 8192
        assert config.timeout == 30  # Default
        assert config.max_retries == 3  # Default
        assert config.rate_limit_per_minute == 60  # Default
        assert config.is_active is True  # Default

    def test_config_with_optional_fields(self):
        """Test config with all optional fields"""
        config = ProviderConfig(
            provider=ProviderType.OPENAI,
            model_name="gpt-4",
            api_key="key",
            base_url="https://api.openai.com",
            cost_per_1m_input_tokens=0.03,
            cost_per_1m_output_tokens=0.06,
            max_tokens=128000,
            timeout=60,
            max_retries=5,
            rate_limit_per_minute=100,
            is_active=False,
            health_score=0.8
        )
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.rate_limit_per_minute == 100
        assert config.is_active is False
        assert config.health_score == 0.8


class TestRoutingDecision:
    """Test RoutingDecision model"""

    def test_create_routing_decision(self):
        """Test creating routing decision"""
        decision = RoutingDecision(
            request_id="req-123",
            selected_provider=ProviderType.GLM,
            selected_model="glm-4-plus",
            routing_score=0.85,
            reasoning="Cost-effective choice for this request",
            cost_estimate_usd=0.001,
            quality_estimate=0.9
        )
        assert decision.request_id == "req-123"
        assert decision.selected_provider == ProviderType.GLM
        assert decision.selected_model == "glm-4-plus"
        assert decision.routing_score == 0.85
        assert decision.reasoning == "Cost-effective choice for this request"
        assert decision.cost_estimate_usd == 0.001
        assert decision.quality_estimate == 0.9
        assert decision.fallback_chain == []  # Default
        assert decision.routing_time_ms == 0  # Default

    def test_routing_decision_with_fallback(self):
        """Test routing decision with fallback chain"""
        decision = RoutingDecision(
            request_id="req-123",
            selected_provider=ProviderType.CLAUDE,
            selected_model="claude-3-5-haiku",
            routing_score=0.9,
            reasoning="Primary choice",
            cost_estimate_usd=0.001,
            quality_estimate=0.95,
            fallback_chain=[ProviderType.GLM, ProviderType.DEEPSEEK],
            routing_time_ms=15
        )
        assert len(decision.fallback_chain) == 2
        assert decision.fallback_chain[0] == ProviderType.GLM
        assert decision.routing_time_ms == 15


class TestHealthCheck:
    """Test HealthCheck model"""

    def test_create_healthy_check(self):
        """Test creating healthy check result"""
        health = HealthCheck(
            provider=ProviderType.CLAUDE,
            model="claude-3-5-haiku",
            is_healthy=True,
            response_time_ms=500
        )
        assert health.provider == ProviderType.CLAUDE
        assert health.is_healthy is True
        assert health.response_time_ms == 500
        assert health.error_message is None
        assert isinstance(health.timestamp, datetime)

    def test_create_unhealthy_check(self):
        """Test creating unhealthy check result"""
        health = HealthCheck(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            is_healthy=False,
            response_time_ms=0,
            error_message="Connection timeout"
        )
        assert health.is_healthy is False
        assert health.error_message == "Connection timeout"


class TestPriorityLevel:
    """Test PriorityLevel enum"""

    def test_priority_levels(self):
        """Test priority level values"""
        assert PriorityLevel.LOW.value == "low"
        assert PriorityLevel.NORMAL.value == "normal"
        assert PriorityLevel.HIGH.value == "high"
        assert PriorityLevel.CRITICAL.value == "critical"


class TestAPIResponse:
    """Test APIResponse wrapper"""

    def test_success_response(self):
        """Test successful API response"""
        response = APIResponse(
            success=True,
            data={"result": "success"}
        )
        assert response.success is True
        assert response.data["result"] == "success"
        assert response.error is None
        assert response.request_id is None

    def test_error_response(self):
        """Test error API response"""
        response = APIResponse(
            success=False,
            error="Invalid request"
        )
        assert response.success is False
        assert response.error == "Invalid request"
        assert response.data is None

    def test_response_with_request_id(self):
        """Test API response with request ID"""
        response = APIResponse(
            success=True,
            data={"result": "ok"},
            request_id="req-123"
        )
        assert response.request_id == "req-123"
        assert isinstance(response.timestamp, datetime)


class TestQueueItem:
    """Test QueueItem model"""

    def test_create_queue_item(self):
        """Test creating queue item"""
        request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Test")]
        )
        item = QueueItem(
            request_id="req-123",
            request_data=request,
            priority=PriorityLevel.NORMAL
        )
        assert item.request_id == "req-123"
        assert item.priority == PriorityLevel.NORMAL
        assert item.attempts == 0  # Default
        assert item.max_attempts == 3  # Default
        assert item.last_attempt is None
        assert isinstance(item.created_at, datetime)


class TestAlert:
    """Test Alert model"""

    def test_create_alert(self):
        """Test creating alert"""
        alert = Alert(
            alert_type="rate_limit",
            severity="warning",
            title="Rate limit exceeded",
            message="Provider CLAUDE exceeded rate limit"
        )
        assert alert.alert_type == "rate_limit"
        assert alert.severity == "warning"
        assert alert.title == "Rate limit exceeded"
        assert alert.resolved is False
        assert alert.resolved_at is None
        assert isinstance(alert.alert_id, str)

    def test_alert_with_metadata(self):
        """Test alert with metadata"""
        alert = Alert(
            alert_type="health_check",
            severity="error",
            title="Provider unhealthy",
            message="Provider OPENAI failed health check",
            metadata={"provider": "openai", "error": "timeout"}
        )
        assert alert.metadata["provider"] == "openai"
        assert alert.metadata["error"] == "timeout"


class TestStreamChunk:
    """Test StreamChunk model"""

    def test_create_stream_chunk(self):
        """Test creating stream chunk"""
        chunk = StreamChunk(
            request_id="req-123",
            chunk_id=1,
            content="Hello"
        )
        assert chunk.request_id == "req-123"
        assert chunk.chunk_id == 1
        assert chunk.content == "Hello"
        assert chunk.is_final is False  # Default

    def test_final_stream_chunk(self):
        """Test final stream chunk"""
        chunk = StreamChunk(
            request_id="req-123",
            chunk_id=10,
            content="!",
            is_final=True
        )
        assert chunk.is_final is True
