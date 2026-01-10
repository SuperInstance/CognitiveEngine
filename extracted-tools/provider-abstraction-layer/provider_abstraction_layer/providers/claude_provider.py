"""
Claude Haiku 4.5 API provider implementation
"""

import json
import time
from typing import Dict, Any, AsyncGenerator
import httpx

from .base import BaseProvider
from ..models import GenerationRequest, GenerationResponse, ChatMessage
from ..utils.logger import logger


class ClaudeProvider(BaseProvider):
    """Claude Haiku 4.5 API provider - Fast, efficient, and cost-effective from Anthropic"""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries
        self.anthropic_version = "2023-06-01"

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion using Claude Haiku API"""
        self.validate_request(request)

        async def api_call():
            request_data = self._prepare_request_data(request)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._get_headers(),
                    json=request_data
                )
                response.raise_for_status()

                response_data = response.json()
                response_time_ms = int((time.time() - start_time) * 1000)

                return response_data, response_time_ms

        start_time = time.time()
        return await self._make_request_with_tracking(request, api_call)

    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate text completion with streaming using Claude Haiku API"""
        self.validate_request(request)

        request_data = self._prepare_request_data(request)
        request_data["stream"] = True

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/messages",
                    headers=self._get_headers(),
                    json=request_data
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            if data == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(data)
                                if chunk_data.get("type") == "content_block_delta":
                                    delta = chunk_data.get("delta", {})
                                    if "text" in delta:
                                        yield delta["text"]
                            except json.JSONDecodeError:
                                continue

            except Exception as e:
                logger.error(f"Claude streaming error: {str(e)}")
                raise

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request data for Claude Haiku API"""
        # Claude uses a slightly different message format
        messages = []
        system_message = None

        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        request_data = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
            "top_p": request.top_p
        }

        # Add system message if present
        if system_message:
            request_data["system"] = system_message

        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Claude Haiku API response"""
        if response_data.get("type") != "message":
            raise ValueError("Invalid response format: not a message type")

        content_blocks = response_data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        return {
            "content": content,
            "usage": response_data.get("usage", {}),
            "stop_reason": response_data.get("stop_reason"),
            "model": response_data.get("model"),
            "id": response_data.get("id"),
            "created": response_data.get("created")
        }

    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        """Extract generated content from Claude Haiku response"""
        content_blocks = response_data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")
        return content

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from Claude Haiku response"""
        if "usage" in response_data and "input_tokens" in response_data["usage"]:
            return response_data["usage"]["input_tokens"]
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from Claude Haiku response"""
        if "usage" in response_data and "output_tokens" in response_data["usage"]:
            return response_data["usage"]["output_tokens"]

        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for Claude Haiku usage"""
        input_cost = (input_tokens / 1_000_000) * self.config.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * self.config.cost_per_1m_output_tokens
        return input_cost + output_cost

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for Claude Haiku API"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.anthropic_version,
            "User-Agent": "LucidDreamer-Router/1.0"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Claude Haiku API"""
        start_time = time.time()

        try:
            # Create minimal test request
            test_request = GenerationRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=5,
                temperature=0.1
            )

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._get_headers(),
                    json=self._prepare_request_data(test_request)
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    response_data = response.json()
                    usage = response_data.get("usage", {})

                    return {
                        "status": "healthy",
                        "response_time_ms": response_time_ms,
                        "model": self.model_name,
                        "test_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                        "timestamp": time.time()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}: {response.text[:200]}",
                        "response_time_ms": response_time_ms,
                        "timestamp": time.time()
                    }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": int((time.time() - start_time) * 1000),
                "timestamp": time.time()
            }

    def supports_streaming(self) -> bool:
        """Claude Haiku supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """Claude Haiku supports function calling"""
        return True

    def get_rate_limits(self) -> Dict[str, int]:
        """Get Claude Haiku rate limits"""
        return {
            "requests_per_minute": self.config.rate_limit_per_minute,
            "tokens_per_minute": 500_000,  # Claude Haiku typical limit
            "max_concurrent_requests": 10
        }

    def estimate_request_cost(self, request: GenerationRequest) -> float:
        """Estimate cost for a request before making it"""
        input_tokens = self._count_messages_tokens(request.messages)
        estimated_output_tokens = request.max_tokens or 512  # Default estimate

        return self.calculate_cost(input_tokens, estimated_output_tokens)

    def is_cost_effective_for(self, request: GenerationRequest) -> bool:
        """Determine if Claude Haiku is cost-effective for this request type"""
        # Claude Haiku is particularly good for:
        # - Conversational AI
        # - Content summarization
        # - Text analysis and classification
        # - Quick responses
        # - Multi-language support

        content = " ".join(msg.content for msg in request.messages).lower()

        # Check for content types where Claude Haiku excels
        conversational_indicators = [
            "conversation", "chat", "dialogue", "discuss", "talk",
            "ask", "tell me", "what do you think", "help me understand"
        ]

        summarization_indicators = [
            "summarize", "summary", "key points", "highlights", "main ideas",
            "brief", "concise", "overview", "essence"
        ]

        analysis_indicators = [
            "analyze", "analysis", "classify", "categorize", "evaluate",
            "compare", "contrast", "assess", "review"
        ]

        has_conversational = any(indicator in content for indicator in conversational_indicators)
        has_summarization = any(indicator in content for indicator in summarization_indicators)
        has_analysis = any(indicator in content for indicator in analysis_indicators)

        # Check if content is relatively short (Haiku is optimized for quick responses)
        estimated_tokens = self._count_messages_tokens(content)
        is_short_content = estimated_tokens < 2000

        return has_conversational or has_summarization or has_analysis or is_short_content

    def get_quality_score(self) -> float:
        """Get Claude Haiku quality score (0.0 to 1.0)"""
        # Claude Haiku provides excellent quality for the speed and cost
        return 0.87  # High quality with excellent speed

    def get_performance_characteristics(self) -> Dict[str, Any]:
        """Get Claude Haiku performance characteristics"""
        return {
            "average_response_time_ms": 600,  # Very fast response time
            "throughput_tokens_per_second": 200,
            "context_window": 8192,
            "supported_languages": ["en", "es", "fr", "de", "ja", "ko", "zh", "pt", "it", "ru"],
            "specialties": [
                "conversation",
                "summarization",
                "text_analysis",
                "classification",
                "quick_responses",
                "multilingual_support"
            ],
            "cost_tier": "low",  # $0.25/1M input tokens
            "quality_tier": "high",
            "speed_tier": "very_fast",
            "strengths": [
                "Exceptional conversational abilities",
                "Fast response times",
                "Strong summarization skills",
                "Excellent text analysis",
                "Wide language support",
                "Consistent performance"
            ]
        }

    def get_optimal_temperature_range(self) -> Dict[str, float]:
        """Get optimal temperature range for Claude Haiku"""
        return {
            "creative": 0.9,
            "balanced": 0.7,
            "precise": 0.3,
            "analytical": 0.2  # Lower temperature for analytical tasks
        }

    def analyze_request_characteristics(self, request: GenerationRequest) -> Dict[str, Any]:
        """Analyze request characteristics for routing decisions"""
        content = " ".join(msg.content for msg in request.messages)
        estimated_tokens = self._count_messages_tokens(content)

        # Analyze content characteristics
        characteristics = {
            "is_conversational": any(word in content.lower() for word in ["hello", "hi", "how are", "what do you", "tell me"]),
            "is_summarization": any(word in content.lower() for word in ["summarize", "summary", "key points", "main"]),
            "is_analysis": any(word in content.lower() for word in ["analyze", "analysis", "evaluate", "compare"]),
            "is_classification": any(word in content.lower() for word in ["classify", "categorize", "type of"]),
            "content_length": estimated_tokens,
            "is_multilingual": self._detect_multilingual_content(content),
            "has_structured_data": self._has_structured_data(content)
        }

        # Calculate suitability score for Claude Haiku
        suitability_score = 0.0
        if characteristics["is_conversational"]:
            suitability_score += 0.3
        if characteristics["is_summarization"]:
            suitability_score += 0.25
        if characteristics["is_analysis"]:
            suitability_score += 0.2
        if characteristics["is_classification"]:
            suitability_score += 0.15
        if characteristics["content_length"] < 2000:  # Prefers shorter content
            suitability_score += 0.1

        return {
            "suitability_score": min(1.0, suitability_score),
            "characteristics": characteristics,
            "recommended": suitability_score > 0.4,
            "optimization_tips": self._get_optimization_tips(characteristics)
        }

    def _detect_multilingual_content(self, content: str) -> bool:
        """Detect if content contains multiple languages"""
        # Simple heuristic: check for non-ASCII characters
        non_ascii_count = sum(1 for char in content if ord(char) > 127)
        return non_ascii_count > len(content) * 0.1  # More than 10% non-ASCII

    def _has_structured_data(self, content: str) -> bool:
        """Check if content contains structured data"""
        structured_indicators = ["list", "table", "json", "xml", "csv", "format", "structure"]
        return any(indicator in content.lower() for indicator in structured_indicators)

    def _get_optimization_tips(self, characteristics: Dict[str, Any]) -> list[str]:
        """Get optimization tips based on request characteristics"""
        tips = []

        if characteristics["is_conversational"]:
            tips.append("Claude Haiku excels at natural conversation")
        if characteristics["is_summarization"]:
            tips.append("Excellent for quick, accurate summarization")
        if characteristics["content_length"] > 4000:
            tips.append("Consider splitting long content for better performance")
        if characteristics["is_multilingual"]:
            tips.append("Strong multilingual capabilities")
        if characteristics["has_structured_data"]:
            tips.append("Good at analyzing and restructuring data")

        return tips