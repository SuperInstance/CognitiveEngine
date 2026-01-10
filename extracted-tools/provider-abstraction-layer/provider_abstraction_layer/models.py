"""
Data models for the multi-provider routing system
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class ProviderType(str, Enum):
    """Supported provider types"""
    GLM = "glm"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OPENAI = "openai"
    DEEPINFRA = "deepinfra"


class RequestStatus(str, Enum):
    """Request status types"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"


class PriorityLevel(str, Enum):
    """Request priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SpecialtyModel(str, Enum):
    """DeepInfra specialty models"""
    WIZARDLM = "wizardlm-2-8x22b"
    NEMOTRON = "nemotron-4-340b"
    HERMES = "hermes-3-405b"


class ProviderConfig(BaseModel):
    """Provider configuration"""
    provider: ProviderType
    model_name: str
    api_key: str
    base_url: str
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float
    max_tokens: int
    timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    is_active: bool = True
    health_score: float = 1.0
    last_health_check: Optional[datetime] = None


class ChatMessage(BaseModel):
    """Chat message"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None


class GenerationRequest(BaseModel):
    """Text generation request"""
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    preferred_provider: Optional[ProviderType] = None
    force_specialty_model: Optional[SpecialtyModel] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError('Messages cannot be empty')
        return v

    @validator('temperature')
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError('Temperature must be between 0 and 2')
        return v


class GenerationResponse(BaseModel):
    """Text generation response"""
    request_id: str
    content: str
    provider_used: ProviderType
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    processing_time_ms: int
    cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Routing decision metadata"""
    request_id: str
    selected_provider: ProviderType
    selected_model: str
    routing_score: float
    reasoning: str
    cost_estimate_usd: float
    quality_estimate: float
    fallback_chain: List[ProviderType] = Field(default_factory=list)
    routing_time_ms: int


class CostTracking(BaseModel):
    """Cost tracking information"""
    request_id: str
    provider: ProviderType
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class BudgetStatus(BaseModel):
    """Budget status information"""
    date: datetime
    daily_budget_usd: float
    spent_usd: float
    remaining_usd: float
    percentage_used: float
    warning_threshold: float
    hard_limit: float
    is_warning_reached: bool
    is_limit_reached: bool
    projected_daily_usage: Optional[float] = None


class ProviderMetrics(BaseModel):
    """Provider performance metrics"""
    provider: ProviderType
    model: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    average_tokens_per_request: float
    total_cost_usd: float
    uptime_percentage: float
    error_rate: float
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality_score: Optional[float] = None


class HealthCheck(BaseModel):
    """Provider health check result"""
    provider: ProviderType
    model: str
    is_healthy: bool
    response_time_ms: int
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueueItem(BaseModel):
    """Queue item for request processing"""
    request_id: str
    request_data: GenerationRequest
    priority: PriorityLevel
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    max_attempts: int = 3
    last_attempt: Optional[datetime] = None
    estimated_cost: Optional[float] = None
    assigned_provider: Optional[ProviderType] = None


class Alert(BaseModel):
    """System alert"""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str
    severity: str  # info, warning, error, critical
    title: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class UsageAnalytics(BaseModel):
    """Usage analytics data"""
    date: datetime
    hour: int
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    provider_breakdown: Dict[ProviderType, Dict]
    average_response_time_ms: float
    peak_requests_per_minute: int
    cache_hit_rate: Optional[float] = None


class PerformanceReport(BaseModel):
    """Performance report"""
    report_date: datetime
    period_hours: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_cost_usd: float
    average_response_time_ms: float
    provider_performance: Dict[ProviderType, ProviderMetrics]
    cost_savings_vs_openai: Optional[float] = None
    quality_score_trend: Optional[List[float]] = None
    recommendations: List[str] = Field(default_factory=list)


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StreamChunk(BaseModel):
    """Streaming response chunk"""
    request_id: str
    chunk_id: int
    content: str
    is_final: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)