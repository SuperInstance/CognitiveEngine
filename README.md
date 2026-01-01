# Lucid Dreamer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node Version](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen)](https://nodejs.org)
[![pnpm](https://img.shields.io/badge/pnpm-%3E%3D8.0.0-orange)](https://pnpm.io)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)](https://typescriptlang.org)

Cognitive intelligence system for advanced abstraction, pattern recognition, and insight generation.

## Overview

Lucid Dreamer is a backend AI system that processes information through multiple abstraction layers to discover patterns, generate insights, and create novel connections. It's the "cognitive engine" of the SuperInstance ecosystem.

### Key Features

- **5-Level Abstraction** - Process data through hierarchical cognitive layers
- **Pattern Recognition** - Detect complex patterns across datasets
- **Insight Generation** - Generate novel insights and hypotheses
- **Knowledge Synthesis** - Combine disparate information into coherent understanding
- **Dream Mode** - Generative exploration of idea spaces
- **Memory Integration** - Work with MemorySystem for persistent knowledge
- **Tensor Operations** - Knowledge tensor manipulation
- **Streaming API** - Real-time cognitive processing

## Architecture

```
                    ┌─────────────────────────┐
                    │     Lucid Dreamer       │
                    │      Cognitive Core     │
                    └───────────┬─────────────┘
                                │
    ┌───────────────────────────┼───────────────────────────┐
    │                           │                           │
┌───▼────┐              ┌──────▼──────┐              ┌────▼─────┐
│ Level 1│              │   Level 2   │              │  Level 3 │
│Raw Data│ ─────────▶   │  Patterns   │  ─────────▶  │ Concepts │
└────────┘              └─────────────┘              └──────────┘
                                                        │
    ┌───────────────────────────┼───────────────────────────┐
    │                           │                           │
┌───▼──────┐              ┌─────▼──────┐              ┌────▼─────┐
│ Level 4  │              │   Level 5  │              │  Dream   │
│Contextual│  ─────────▶  │ Abstract   │  ─────────▶  │  Mode    │
│Meanings  │              │ Principles │              │Generator │
└──────────┘              └────────────┘              └──────────┘
```

## Quick Start

### Prerequisites

- Node.js 18+
- PostgreSQL (for knowledge storage)
- pnpm 8+

### Installation

```bash
# Clone the repository
git clone https://github.com/SuperInstance/LucidDreamer.git
cd LucidDreamer

# Install dependencies
pnpm install

# Start PostgreSQL
docker-compose up -d

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the service
pnpm start
```

### Running in Production

```bash
# Build
pnpm build

# Start with PM2
npx pm2 start dist/index.js --name lucid-dreamer
```

## Usage

### Basic Abstraction

```typescript
import { LucidDreamer } from '@superinstance/lucid-dreamer';

const dreamer = new LucidDreamer({
  connectionString: process.env.DATABASE_URL
});

// Process data through abstraction levels
const insights = await dreamer.dream({
  input: 'User engagement metrics showing 30% drop',
  context: { domain: 'product-analytics' }
});

console.log(insights);
// {
//   patterns: ['engagement drops correlate with feature changes'],
//   concepts: ['user friction points'],
//   hypotheses: ['new UI may be causing confusion']
// }
```

### Pattern Recognition

```typescript
// Detect patterns in data
const patterns = await dreamer.recognizePatterns({
  data: [
    { timestamp: '2024-01-01', metric: 100 },
    { timestamp: '2024-01-02', metric: 95 },
    { timestamp: '2024-01-03', metric: 90 }
  ],
  patternTypes: ['trend', 'anomaly', 'cycle']
});
```

### Dream Mode

```typescript
// Generative exploration
const dreams = await dreamer.enterDreamMode({
  seed: 'sustainable energy solutions',
  explorationDepth: 5,
  noveltyThreshold: 0.7
});

// Returns novel idea combinations
```

## Project Structure

```
lucid-dreamer/
├── src/
│   ├── core/                   # Core cognitive engine
│   │   ├── dreamer.ts          # Main LucidDreamer class
│   │   ├── abstraction.ts      # Abstraction layer processor
│   │   └── consciousness.ts    # Consciousness simulation
│   ├── levels/                 # Abstraction levels
│   │   ├── level1-data.ts      # Raw data processing
│   │   ├── level2-patterns.ts  # Pattern recognition
│   │   ├── level3-concepts.ts  # Concept extraction
│   │   ├── level4-context.ts   # Contextual meaning
│   │   └── level5-principles.ts# Abstract principles
│   ├── patterns/               # Pattern detection
│   │   ├── detector.ts         # Pattern detection engine
│   │   └── clustering.ts       # Clustering algorithms
│   ├── insights/               # Insight generation
│   │   ├── generator.ts        # Insight generator
│   │   └── scorer.ts           # Insight relevance scoring
│   ├── dream/                  # Dream mode
│   │   ├── explorer.ts         # Idea space explorer
│   │   └── synthesizer.ts      # Idea synthesizer
│   ├── storage/                # Knowledge persistence
│   │   ├── postgres.ts         # PostgreSQL interface
│   │   └── tensor.ts           # Tensor operations
│   ├── api/                    # HTTP API
│   │   ├── routes.ts           # API routes
│   │   └── middleware.ts       # Express middleware
│   └── types/                  # TypeScript definitions
├── docker/
│   └── docker-compose.yml
├── migrations/                 # Database migrations
└── tests/                      # Test suite
```

## API Reference

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/dream` | POST | Process input through dreamer |
| `/api/patterns` | POST | Detect patterns |
| `/api/insights` | GET | Retrieve recent insights |
| `/api/levels/:id` | GET | Get abstraction level output |
| `/api/dream-mode` | POST | Enter generative dream mode |

### WebSocket API

```javascript
const ws = new WebSocket('ws://localhost:4000/ws');

// Subscribe to insight stream
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'insights'
}));

// Receive real-time insights
ws.onmessage = (event) => {
  const insight = JSON.parse(event.data);
  console.log('New insight:', insight);
};
```

## Configuration

### Environment Variables

```bash
# Server
PORT=4000
HOST=0.0.0.0
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/luciddreamer

# Abstraction
MAX_ABSTRACTION_LEVELS=5
PATTERN_CONFIDENCE_THRESHOLD=0.7
INSIGHT_NOVELTY_THRESHOLD=0.6

# Dream Mode
DREAM_EXPLORATION_DEPTH=5
DREAM_MAX_COMBINATIONS=100

# Caching
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM Integration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Cognitive Levels

### Level 1: Raw Data
- Input normalization
- Data cleaning
- Feature extraction

### Level 2: Patterns
- Statistical patterns
- Temporal patterns
- Correlation detection

### Level 3: Concepts
- Concept extraction
- Semantic clustering
- Category formation

### Level 4: Contextual Meanings
- Context integration
- Situational awareness
- Pragmatic interpretation

### Level 5: Abstract Principles
- First principles
- Universal patterns
- Meta-insights

## Technologies

- **Node.js 18+** - Runtime
- **TypeScript 5** - Type safety
- **Express** - Web framework
- **PostgreSQL** - Knowledge storage
- **Redis** - Caching
- **Tensor Ops** - Knowledge tensor operations
- **OpenAI/Anthropic** - LLM integration

## License

MIT

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md)

## Support

- GitHub Issues: https://github.com/SuperInstance/LucidDreamer/issues
- Documentation: https://docs.superinstance.dev/lucid-dreamer

---

**SuperInstance** - Modular toolkit ecosystem for intelligent applications.
