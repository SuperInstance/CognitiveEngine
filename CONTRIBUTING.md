# Contributing to Lucid Dreamer

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/SuperInstance/LucidDreamer.git
cd LucidDreamer

# Install dependencies
pnpm install

# Start infrastructure
docker-compose up -d

# Run in development
pnpm dev
```

## Running Tests

```bash
# Run tests
pnpm test

# Run with coverage
pnpm test:coverage

# Watch mode
pnpm test --watch
```

## Architecture

Lucid Dreamer processes information through 5 cognitive levels:

1. **Level 1**: Raw data processing
2. **Level 2**: Pattern recognition
3. **Level 3**: Concept extraction
4. **Level 4**: Contextual meaning
5. **Level 5**: Abstract principles

When contributing, please consider which level your changes affect and ensure compatibility with adjacent levels.

## Code Style

- Use TypeScript for all new code
- Document cognitive algorithms
- Add examples for insight patterns
- Keep functions pure where possible

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests with cognitive examples
5. Submit a pull request
