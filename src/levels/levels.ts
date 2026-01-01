/**
 * Abstraction Levels
 *
 * Lucid Dreamer processes information through 5 cognitive levels:
 */

export const ABSTRACTION_LEVELS = [
  {
    level: 1,
    name: 'Raw Data',
    description: 'Input normalization and feature extraction'
  },
  {
    level: 2,
    name: 'Patterns',
    description: 'Statistical and temporal pattern detection'
  },
  {
    level: 3,
    name: 'Concepts',
    description: 'Semantic clustering and concept formation'
  },
  {
    level: 4,
    name: 'Contextual Meanings',
    description: 'Context integration and pragmatic interpretation'
  },
  {
    level: 5,
    name: 'Abstract Principles',
    description: 'First principles and meta-insights'
  }
] as const;
