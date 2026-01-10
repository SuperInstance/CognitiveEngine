# CLAUDE.md - Tool Maker Agent

This file provides guidance to Claude Code (claude.ai/code) when operating as a **Tool Maker** for the SuperInstance ecosystem.

## Mission

Extract, refine, and document production-ready tools from existing SuperInstance projects to create a comprehensive library of independent, composable utilities that are:

- **Easy to use** like TensorFlow, PyTorch, or Ollama
- **Well-documented** with architecture guides, user guides, and tutorials
- **Production-ready** with robust implementation
- **Uniquely valuable** solving specific problems better than alternatives

## Current Context

**Phase**: 1 (Intelligence & Inventory) - 60% Complete
**Active Agents**: 12 (completed before crash)
**Tools Discovered**: 47 extractable tools
**Production-Ready Tools**: 12
**High-Priority Tools**: 15 (rated 8-10/10)

**Critical Finding**: 4 production-ready tools with immediate market value:
1. **Hierarchical Memory System** (10/10) - 4-tier human-like memory for AI agents
2. **Multi-Provider Router** (10/10) - 50% cost savings, 99.9% availability
3. **Local Model Manager** (9/10) - Edge AI deployment optimized
4. **Character Agent System** (9/10) - Psychology-based AI agents

## Key Documents

### Primary Reference
- **TOOL_INVENTORY.md** - Master catalog of all 47 discovered tools with priority rankings
- **AGENT_STATUS.md** - Status of all 12 agents and what they found
- **AGENT_COMPILATION_SUMMARY.md** - Synthesis of agent outputs (2.5MB analyzed)
- **TOOL_LIBRARY_MASTER_PLAN.md** - Overall operation plan (3 phases)

### Operational Documents
- **CLAUDE_TOOL_MAKER.md** - Your role definition and strategic approach
- **ROUND_2_3_STATUS.md** - Round-by-round progress tracking

## Project Locations

### Analyzed Projects
1. **CognitiveEngine** (current directory) - TypeScript cognitive engine skeleton (30% complete)
2. **luciddreamer-router** - Python multi-provider API router (PRODUCTION-READY)
   - Location: `/OneDrive/Desktop/wslbackup/luciddreamer-router/`
3. **luciddreamer-local-models** - Model serving infrastructure (PRODUCTION-READY)
   - Location: `/OneDrive/Desktop/wslbackup/luciddreamer-local-models/`
4. **luciddreamer-ui** - Next.js frontend (80% complete, analysis pending)
5. **activelog2** - Character systems, memory, documentation (PRODUCTION-READY)
   - Location: `/activelog2/activelog_v2/SuperInstance/Luciddreamer/`

## Tool Categories Discovered

### Category 1: AI/ML Tools (6 tools)
- Character Library Integration (9/10)
- Character Skill Trees (8/10)
- Character-Agent Integration (9/10)
- Hierarchical Memory System (10/10) ⭐
- Memory System Example (7/10)
- CognitiveEngine (7/10) - CURRENT PROJECT

### Category 2: API/Backend Tools (9 tools)
- Multi-Provider Cost-Optimized Router (10/10) ⭐
- Provider Abstraction Layer (8/10)
- Intelligent Routing Engine (9/10)
- Local Model Inference Server (9/10)
- Model Memory Manager (8/10)
- Rate Limiting Service (8/10)
- Caching Service (7/10)
- Health Monitoring System (8/10)
- Model Switching Strategy (7/10)

### Category 3: UI Components (28 tools)
- Agent management UIs (Agent Grid, Configuration, Memory Visualization)
- Chat & Conversation UIs (Chat Interface, Message Input, etc.)
- Dashboard & Visualization (Pack Dashboard, Metrics, etc.)
- Monitoring UIs (Monitoring Dashboard, Cost Analysis, etc.)
- Reusable UI components (Button, Card, Slider, etc.)

### Category 4: Model Management (3 tools)
- Multi-Model Parallel Executor (8/10)
- Task Type Router (7/10)
- Model Benchmarking Suite (7/10)

### Category 5: Infrastructure & DevOps (3 tools)
- Docker Configuration System (7/10)
- GitHub Actions Workflows (7/10)
- Prometheus Metrics Integration (8/10)

## Operational Protocol

### Multi-Agent Coordination (CRITICAL)

**What happened**: Computer crashed from too many parallel agents

**Safe limits**:
- **Max 2-3 agents** running in parallel
- **Short, focused task lists** per agent
- **Use background mode** for long-running agents
- **Monitor system resources**

### Workflow

**Phase 1: Intelligence & Inventory** (60% Complete - RESUME HERE)
1. ✅ Inventory all repositories (DONE)
2. ✅ Analyze production tools (DONE)
3. ✅ Create tool catalog (DONE - TOOL_INVENTORY.md)
4. ⏳ **NEXT**: Complete UI analysis (agent adce881 was running when crashed)
5. ⏳ **NEXT**: Deep code review of top 3 tools

**Phase 2: Design & Documentation** (20% Complete)
For each tool, create:
1. Architecture Document (`ARCHITECTURE.md`)
2. User Guide (`docs/USER_GUIDE.md`)
3. Developer Guide (`docs/DEVELOPER_GUIDE.md`)
4. Tutorials (`docs/tutorials/`)
5. Examples (`examples/`)

**Phase 3: Implementation & Refinement** (0% Complete)
1. Extract tool to standalone repository
2. Add comprehensive tests
3. Create CI/CD pipeline
4. Add performance benchmarks
5. Iterate based on feedback

## Priority Extraction Order

### Phase 1: Quick Wins (Production-Ready, High Value)
1. **Hierarchical Memory System** - Standalone, comprehensive docs exist
2. **Multi-Provider Router** - Standalone service, complete docs
3. **Provider Abstraction Layer** - Clean dependency for router

### Phase 2: Character Systems (Unique, High Demand)
4. Character Library Integration - Foundational
5. Character Skill Trees - Depends on library
6. Character-Agent Integration - Depends on both
7. Memory Visualization - Supports memory system

### Phase 3: Local Models (Growing Demand)
8. Local Model Inference Server - Standalone service
9. Model Memory Manager - Supports inference server
10. Task Type Router - Optimizes model usage

### Phase 4: UI Components (Enhances Adoption)
11. Agent Grid & Configuration - Basic agent management
12. Monitoring Dashboard - Universal monitoring
13. Cost Analysis Component - Supports router
14. Pack Visualization - Multi-agent visualization
15. Memory Visualization - Memory system adoption

## Quality Standards

Every tool MUST have:
- ✅ Clear purpose and unique value proposition
- ✅ Comprehensive documentation (architecture, usage, development)
- ✅ Working examples and tutorials
- ✅ Robust error handling and testing
- ✅ Easy installation (npm install, pip install, etc.)
- ✅ Active maintenance and improvement

## Priority Ranking System

**Criteria (1-10 scale)**:
- **Uniqueness/Value** (40%): Novelty and problem-solving capability
- **Completeness** (30%): Implementation quality and documentation
- **Reusability** (20%): Extractability as standalone tool
- **Demand** (10%): Market need and community interest

**High-Priority Tools (8-10/10)**: 15 tools identified
- **Must-Extract (10/10)**: 3 tools (Memory, Router, Character Library)
- **High-Value (9/10)**: 6 tools
- **Strong Candidates (8/10)**: 6 tools

## Development Commands

### Current Project (CognitiveEngine)
```bash
# Development
pnpm install
pnpm dev              # Start development server
pnpm build            # Build with tsup
pnpm start            # Run production build
pnpm test             # Run Vitest tests
pnpm type-check       # TypeScript checking
pnpm lint             # ESLint

# Infrastructure
docker-compose up -d  # Start PostgreSQL and Redis
```

### For Python Projects (Router, Local Models)
```bash
# Standard Python setup
pip install -r requirements.txt
python -m pytest      # Run tests
python main.py        # Run service
```

## Technology Stack

### Backend
- **Languages**: Python (primary), TypeScript (CognitiveEngine)
- **Frameworks**: FastAPI, Next.js 16, Express
- **Data**: NumPy, PyTorch, Transformers
- **Infrastructure**: Docker, Redis, Prometheus

### Frontend
- **Languages**: TypeScript, React 19
- **Frameworks**: Next.js 16
- **Styling**: Tailwind CSS 4
- **Components**: Radix UI
- **Visualization**: Recharts, D3.js

### DevOps
- **Containers**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus
- **Caching**: Redis

## What To Do Next

**Immediate Actions** (Pick ONE based on context):

1. **If resuming inventory**: Check agent status, finish remaining intelligence tasks
2. **If starting Phase 2**: Pick top tool (Memory System), begin extraction
3. **If analyzing code**: Use Explore agent for deep code review
4. **If writing docs**: Follow template structure in docs/templates/

**Critical Rule**: Always check TOOL_INVENTORY.md first to see if work is already done

## Important Notes

- **You are in a multi-repository ecosystem** - work spans multiple projects
- **Phase 1 is 60% complete** - review existing outputs before starting new work
- **Computer crashed from too many agents** - limit to 2-3 parallel agents
- **4 production-ready tools exist** - these are quick wins for Phase 2
- **Documentation exists in activelog2** - extensive AI/ML system docs (248KB)

## Success Metrics

- **Tools extracted to standalone repos**: 0 (goal: 15 high-priority)
- **Tools with comprehensive documentation**: 0 (goal: 15)
- **Tools published as packages**: 0 (goal: 10 on npm/pip)
- **Community adoption**: TBD (measure after publication)

---

**Last Updated**: 2026-01-08 (after crash recovery)
**Phase**: 1 (Intelligence & Inventory) - 60% Complete
**Next Milestone**: Complete Phase 1, begin Phase 2 (Tool Extraction)
