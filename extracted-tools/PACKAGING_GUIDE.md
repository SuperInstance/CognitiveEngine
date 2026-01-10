# Tool Packaging Guide - Complete Instructions

**Date**: 2026-01-09
**Session**: Round 2 Extraction
**Purpose**: Step-by-step packaging instructions for all 9 extracted tools

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Backend Tools Packaging](#backend-tools-packaging)
   - [Rate Limiting Service](#1-rate-limiting-service)
   - [Caching Service](#2-caching-service)
   - [Health Monitoring System](#3-health-monitoring-system)
   - [Provider Abstraction Layer](#4-provider-abstraction-layer)
   - [Model Switching Strategy](#5-model-switching-strategy)
3. [UI Components Extraction](#ui-components-extraction)
4. [Testing Checklist](#testing-checklist)
5. [Publication Checklist](#publication-checklist)

---

## Prerequisites

### Required Tools

```bash
# Python packaging tools
pip install setuptools wheel build twine

# For testing
pip install pytest pytest-cov pytest-asyncio

# For documentation
pip install sphinx sphinx-rtd-theme
```

### Directory Structure

```bash
extracted-tools/
├── rate-limiting-service/
├── caching-service/
├── health-monitoring-system/
├── provider-abstraction-layer/
├── model-switching-strategy/
└── packaging-scripts/
```

---

## Backend Tools Packaging

### 1. Rate Limiting Service ⭐ (Easiest - Start Here)

**Estimated Time**: 2 hours
**Difficulty**: ⭐☆☆☆☆

#### Step 1: Copy Source File

```bash
cd /mnt/c/users/casey/luciddreamer/extracted-tools/rate-limiting-service

# Create package structure
mkdir -p rate_limiting

# Copy source file
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/utils/rate_limiter.py \
   rate_limiting/limiter.py
```

#### Step 2: Remove Router Dependencies

Edit `rate_limiting/limiter.py`:

```python
# REMOVE these lines (lines 13-16):
from ..models import ProviderType
from ..config import get_settings

settings = get_settings()

# REPLACE with:
from enum import Enum
import os

class ProviderType(str, Enum):
    GLM = "glm"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OPENAI = "openai"
    DEEPINFRA = "deepinfra"

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
```

Also update `__init__` (line 33):

```python
# CHANGE:
self.redis_url = settings.redis.url

# TO:
self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
```

#### Step 3: Create Package Files

```bash
# Create __init__.py
cat > rate_limiting/__init__.py << 'EOF'
"""
Rate Limiting Service
Token bucket algorithm for API rate limiting
"""

from .limiter import RateLimiter, RateLimitRule, rate_limiter

__version__ = "1.0.0"
__all__ = ["RateLimiter", "RateLimitRule", "rate_limiter"]
EOF
```

#### Step 4: Create setup.py

```bash
cat > setup.py << 'EOF'
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rate-limiting-service",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Token bucket algorithm for API rate limiting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/rate-limiting-service",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "redis>=4.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
)
EOF
```

#### Step 5: Create pyproject.toml

```bash
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "rate-limiting-service"
version = "1.0.0"
description = "Token bucket algorithm for API rate limiting"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
dependencies = [
    "redis>=4.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
]
EOF
```

#### Step 6: Create Tests

```bash
mkdir tests
cat > tests/test_limiter.py << 'EOF'
import pytest
from rate_limiting import RateLimiter, RateLimitRule, ProviderType

@pytest.mark.asyncio
async def test_rate_limit_check():
    limiter = RateLimiter()
    can_proceed, remaining = await limiter.check_rate_limit(
        ProviderType.GLM
    )
    assert can_proceed is True
    assert 'minute' in remaining

@pytest.mark.asyncio
async def test_user_rate_limit():
    limiter = RateLimiter()
    rule = RateLimitRule(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000
    )
    limiter.set_user_rate_limit("test_user", rule)

    can_proceed, remaining = await limiter.check_rate_limit(
        ProviderType.GLM,
        user_id="test_user"
    )
    assert can_proceed is True
    assert remaining['minute'] == 9
EOF
```

#### Step 7: Build and Test

```bash
# Install in development mode
pip install -e .

# Run tests
pytest tests/ -v

# Build distribution
python -m build

# Check distribution
twine check dist/*
```

#### Step 8: Publish (Optional)

```bash
# Create PyPI account first
# Then publish:
twine upload dist/*
```

---

### 2. Caching Service

**Estimated Time**: 2 hours
**Difficulty**: ⭐☆☆☆☆

Follow similar steps to Rate Limiting Service:

```bash
cd /mnt/c/users/casey/luciddreamer/extracted-tools/caching-service

# Create structure
mkdir -p caching_service

# Copy source
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/utils/cache.py \
   caching_service/cache.py
```

#### Key Changes Needed

1. **Remove router dependencies** (same as rate limiter)
2. **Add simplified models**:

```python
# Add to caching_service/models.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class GenerationRequest:
    messages: List[ChatMessage]
    temperature: float
    top_p: float
    max_tokens: Optional[int]

@dataclass
class GenerationResponse:
    request_id: str
    content: str
    provider_used: str
    model_used: str
    # ... other fields
```

3. **Update imports in cache.py**
4. **Create setup.py, pyproject.toml** (similar to rate limiter)
5. **Create tests**

---

### 3. Health Monitoring System

**Estimated Time**: 3 hours
**Difficulty**: ⭐⭐☆☆☆

```bash
cd /mnt/c/users/casey/luciddreamer/extracted-tools/health-monitoring-system

# Create structure
mkdir -p health_monitor

# Copy source
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/utils/health_checker.py \
   health_monitor/checker.py
```

#### Key Changes Needed

1. **Remove router dependencies**
2. **Add ProviderType, ProviderConfig, HealthCheck models**
3. **Replace logger with standard logging**
4. **Create setup.py with httpx dependency**

```python
install_requires=[
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
]
```

---

### 4. Provider Abstraction Layer

**Estimated Time**: 6 hours
**Difficulty**: ⭐⭐⭐☆☆

This is the most complex backend tool.

```bash
cd /mnt/c/users/casey/luciddreamer/extracted-tools/provider-abstraction-layer

# Create structure
mkdir -p provider_abstraction_layer/{providers,models}

# Copy files
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/models.py \
   provider_abstraction_layer/models/__init__.py

cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/providers/base.py \
   provider_abstraction_layer/base.py

# Copy provider implementations
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-router/src/providers/*.py \
   provider_abstraction_layer/providers/
```

#### Key Changes Needed

1. **Extract only necessary models** from models.py:
   - ProviderType
   - ProviderConfig
   - ChatMessage
   - GenerationRequest
   - GenerationResponse
   - HealthCheck

2. **Remove router-specific models**:
   - RoutingDecision
   - BudgetStatus
   - QueueItem
   - etc.

3. **Update imports** in all provider files
4. **Remove logger dependency** or use standard logging
5. **Create comprehensive tests** for each provider

---

### 5. Model Switching Strategy

**Estimated Time**: 8 hours
**Difficulty**: ⭐⭐⭐⭐☆

Most complex due to tight coupling with model loader.

```bash
cd /mnt/c/users/casey/luciddreamer/extracted-tools/model-switching-strategy

# Create structure
mkdir -p model_switching

# Copy source
cp /mnt/c/users/casey/OneDrive/Desktop/wslbackup/luciddreamer-local-models/src/core/resource_manager.py \
   model_switching/manager.py
```

#### Key Changes Needed

1. **Create abstract interfaces**:

```python
# model_switching/interfaces.py
from abc import ABC, abstractmethod

class GPUMonitor(ABC):
    @abstractmethod
    def get_available_vram(self) -> float:
        pass

    @abstractmethod
    def get_total_vram(self) -> float:
        pass

class ModelLoader(ABC):
    @abstractmethod
    async def load_model(self, model_id: str) -> bool:
        pass

    @abstractmethod
    async def unload_model(self, model_id: str) -> bool:
        pass

    @property
    @abstractmethod
    def models(self) -> dict:
        pass
```

2. **Update ResourceManager**:
   - Accept GPUMonitor and ModelLoader as constructor params
   - Remove direct LLMLoader import
   - Use abstract interfaces

3. **Create mock implementations** for testing:

```python
# model_switching/mocks.py
class MockGPUMonitor(GPUMonitor):
    def __init__(self, total_vram=24.0, used_vram=0.0):
        self.total_vram = total_vram
        self._used_vram = used_vram

    def get_available_vram(self) -> float:
        return self.total_vram - self._used_vram

    def get_total_vram(self) -> float:
        return self.total_vram
```

---

## UI Components Extraction

**Status**: ⚠️ Requires source verification

UI components are listed in TOOL_INVENTORY.md but source files need verification:

### Location Verification

```bash
# Check if UI project exists
ls -la /mnt/c/users/casey/luciddreamer-ui/

# If not found, search for UI components
find /mnt/c/users/casey -name "AgentGrid.tsx" 2>/dev/null
find /mnt/c/users/casey -name "MemoryVisualization.tsx" 2>/dev/null
```

### If Source Files Exist

Follow this pattern for each UI component:

```bash
# Example: Memory Visualization Component
cd /mnt/c/users/casey/luciddreamer/extracted-tools/memory-visualization-component

# Create React package structure
mkdir -p src

# Copy source
cp /path/to/MemoryVisualization.tsx src/

# Create package.json
cat > package.json << 'EOF'
{
  "name": "memory-visualization-component",
  "version": "1.0.0",
  "description": "Advanced visualization of hierarchical memory system",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "jest",
    "storybook": "storybook dev -p 6006"
  },
  "peerDependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "dependencies": {
    "d3": "^7.8.0"
  },
  "devDependencies": {
    "@types/react": "^18.0.0",
    "@types/d3": "^7.4.0",
    "typescript": "^5.0.0"
  }
}
EOF
```

### If Source Files Don't Exist

Recreate components from specifications in TOOL_INVENTORY.md:

1. **Define TypeScript interfaces**
2. **Implement component logic**
3. **Create Storybook stories**
4. **Add example data**

---

## Testing Checklist

### Backend Tools

For each backend tool, ensure:

- [ ] Unit tests for all public methods
- [ ] Async tests with pytest-asyncio
- [ ] Mock external dependencies (Redis, HTTP)
- [ ] Test error handling
- [ ] Test edge cases
- [ ] Code coverage > 80%

```bash
# Example test run
pytest tests/ -v --cov=rate_limiting --cov-report=html
```

### UI Components

For each UI component, ensure:

- [ ] Component renders without errors
- [ ] Props validation
- [ ] User interaction tests
- [ ] Storybook stories
- [ ] Accessibility tests
- [ ] Responsive design tests

```bash
# Example test run
npm test
npm run storybook
```

---

## Publication Checklist

### Before Publishing

- [ ] All tests passing
- [ ] Documentation complete
- [ ] README.md includes:
  - Installation instructions
  - Quick start example
  - API reference
  - Use cases
- [ ] LICENSE file added
- [ ] CHANGELOG.md created
- [ ] Version number set
- [ ] Git tags created

### PyPI Publication (Python)

```bash
# 1. Build
python -m build

# 2. Check
twine check dist/*

# 3. Upload to TestPyPI first
twine upload --repository testpypi dist/*

# 4. Test installation
pip install --index-url https://test.pypi.org/simple/ rate-limiting-service

# 5. Upload to PyPI
twine upload dist/*
```

### npm Publication (JavaScript)

```bash
# 1. Build
npm run build

# 2. Test
npm pack
npm install ./package-name-version.tgz

# 3. Publish
npm publish
```

---

## Post-Publication

### 1. Create GitHub Repository

```bash
# Initialize git
git init
git add .
git commit -m "Initial release v1.0.0"

# Create GitHub repo
gh repo create rate-limiting-service --public

# Push
git remote add origin https://github.com/yourusername/rate-limiting-service.git
git push -u origin main
```

### 2. Add Documentation

- GitHub Wiki
- API documentation (Sphinx/DocFX)
- Examples directory
- CONTRIBUTING.md

### 3. Promote

- Publish to relevant communities
- Write blog post
- Submit to aggregators (Hacker News, Reddit)
- Tweet about it

---

## Summary

### Estimated Total Time

| Tool | Time | Difficulty |
|------|------|------------|
| Rate Limiting | 2h | ⭐☆☆☆☆ |
| Caching Service | 2h | ⭐☆☆☆☆ |
| Health Monitoring | 3h | ⭐⭐☆☆☆ |
| Provider Abstraction | 6h | ⭐⭐⭐☆☆ |
| Model Switching | 8h | ⭐⭐⭐⭐☆ |
| **Total Backend** | **21h** | |
| UI Components | 16h | ⭐⭐⭐☆☆ |
| **Grand Total** | **37h** | |

### Recommended Order

1. **Week 1**: Rate Limiting + Caching (4h) ✅ Quick wins
2. **Week 2**: Health Monitoring (3h) ✅ Easy
3. **Week 3**: Provider Abstraction (6h) ⚠️ Complex
4. **Week 4-5**: Model Switching (8h) ⚠️ Most complex
5. **Week 6**: UI Components (16h) ⚠️ Need source verification

### Success Metrics

- All 9 tools packaged and published
- Combined 100+ GitHub stars
- 1000+ downloads/month
- 10+ external contributors
- Featured in tech newsletters

---

**Last Updated**: 2026-01-09
**Next Review**: After completing first 3 backend tools
**Questions**: Open GitHub issue for support
