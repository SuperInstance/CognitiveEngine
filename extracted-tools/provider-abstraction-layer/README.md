# Provider Abstraction Layer

**Priority**: 8/10
**Status**: Production-Ready
**Original Location**: `luciddreamer-router/src/providers/`

## Overview

A clean, unified abstraction layer for multiple AI API providers. This library provides a consistent interface for interacting with different LLM providers, making it easy to switch between providers or add new ones.

## Features

- **Abstract Base Provider**: Common interface for all providers
- **Consistent Request/Response Models**: Unified data structures
- **Built-in Error Handling**: Retry logic and error management
- **Provider-Specific Optimizations**: Tailored implementations for each provider
- **Easy Provider Addition**: Simple pattern for adding new providers
- **Comprehensive Tracking**: Request logging, token counting, cost calculation
- **Streaming Support**: Async streaming for all providers
- **Health Checks**: Provider health monitoring
- **Request Validation**: Input validation before API calls

## Supported Providers

- GLM-4 (Zhipu AI)
- DeepSeek
- Claude (Anthropic)
- OpenAI
- DeepInfra

## Installation

```bash
pip install provider-abstraction-layer
```

## Quick Start

```python
from provider_abstraction_layer import ProviderConfig, BaseProvider
from provider_abstraction_layer.providers import GLMProvider, OpenAIProvider

# Configure a provider
config = ProviderConfig(
    provider=ProviderType.GLM,
    model_name="glm-4-plus",
    api_key="your-api-key",
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    cost_per_1m_input_tokens=0.5,
    cost_per_1m_output_tokens=0.5,
    max_tokens=128000
)

# Create provider instance
provider = GLMProvider(config)

# Generate text
request = GenerationRequest(
    messages=[
        ChatMessage(role="user", content="Hello, how are you?")
    ],
    temperature=0.7,
    max_tokens=1000
)

response = await provider.generate(request)
print(f"Content: {response.content}")
print(f"Cost: ${response.cost_usd:.6f}")
print(f"Tokens: {response.input_tokens + response.output_tokens}")
```

## Advanced Usage

### Streaming

```python
async for chunk in provider.generate_stream(request):
    print(chunk, end='', flush=True)
```

### Cost Calculation

```python
# Calculate cost before making request
input_tokens = 1000
output_tokens = 500
cost = provider.calculate_cost(input_tokens, output_tokens)
print(f"Estimated cost: ${cost:.6f}")
```

### Health Check

```python
health = await provider.health_check()
print(f"Healthy: {health['is_healthy']}")
print(f"Response time: {health['response_time_ms']}ms")
```

### Rate Limit Info

```python
info = provider.get_rate_limit_info()
print(f"Rate limit: {info['rate_limit_per_minute']} requests/minute")
```

## Adding a New Provider

```python
from provider_abstraction_layer import BaseProvider

class MyProvider(BaseProvider):
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        # Implement generation logic
        pass

    async def generate_stream(self, request: GenerationRequest):
        # Implement streaming logic
        pass

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Implement cost calculation
        pass

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        # Prepare provider-specific request format
        pass

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        # Parse provider-specific response format
        pass

    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        # Extract content from response
        pass
```

## API Reference

### BaseProvider

Abstract base class for all providers.

**Methods**:
- `async generate(request: GenerationRequest) -> GenerationResponse`: Generate text
- `async generate_stream(request: GenerationRequest) -> AsyncGenerator[str, None]`: Generate streaming text
- `calculate_cost(input_tokens: int, output_tokens: int) -> float`: Calculate cost
- `async health_check() -> Dict[str, Any]`: Check provider health
- `get_rate_limit_info() -> Dict[str, Any]`: Get rate limit information
- `validate_request(request: GenerationRequest) -> None`: Validate request
- `supports_streaming() -> bool`: Check if streaming is supported
- `get_provider_info() -> Dict[str, Any]`: Get provider information

### ProviderConfig

Configuration for a provider.

**Fields**:
- `provider: ProviderType`: Provider type
- `model_name: str`: Model name
- `api_key: str`: API key
- `base_url: str`: Base URL for API
- `cost_per_1m_input_tokens: float`: Cost per 1M input tokens
- `cost_per_1m_output_tokens: float`: Cost per 1M output tokens
- `max_tokens: int`: Maximum tokens per request
- `timeout: int`: Request timeout in seconds
- `max_retries: int`: Maximum retry attempts
- `rate_limit_per_minute: int`: Rate limit
- `is_active: bool`: Whether provider is active

### GenerationRequest

Request for text generation.

**Fields**:
- `messages: List[ChatMessage]`: Chat messages
- `temperature: float`: Temperature (0-2)
- `top_p: float`: Top-p sampling (0-1)
- `max_tokens: int`: Maximum tokens to generate
- `stream: bool`: Whether to stream response

### GenerationResponse

Response from text generation.

**Fields**:
- `request_id: str`: Unique request ID
- `content: str`: Generated content
- `provider_used: ProviderType`: Provider used
- `model_used: str`: Model used
- `input_tokens: int`: Input token count
- `output_tokens: int`: Output token count
- `cost_usd: float`: Cost in USD
- `processing_time_ms: int`: Processing time in milliseconds
- `metadata: Dict[str, Any]`: Additional metadata

## Architecture

The abstraction layer follows a clean architecture pattern:

```
BaseProvider (Abstract)
    ├── GLMProvider
    ├── DeepSeekProvider
    ├── ClaudeProvider
    ├── OpenAIProvider
    └── DeepInfraProvider
```

Each provider implements:
- Request generation
- Response parsing
- Cost calculation
- Health checks
- Provider-specific optimizations

## Error Handling

The abstraction layer includes comprehensive error handling:

- **Retry Logic**: Automatic retries with exponential backoff
- **Timeout Handling**: Configurable timeouts
- **Error Context**: Detailed error messages with context
- **Graceful Degradation**: Fallback mechanisms

## Logging

All requests are logged with:
- Request ID
- Provider and model
- Input/output tokens
- Cost
- Processing time
- Errors

## Dependencies

- `pydantic`: Data validation
- `httpx`: Async HTTP client
- `python-dateutil`: Date/time handling

## License

MIT License

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## Support

For issues and questions, please use the GitHub issue tracker.
