/**
 * Core types for Lucid Dreamer
 */

export interface AbstractionLevel {
  level: number;
  name: string;
  description: string;
}

export interface DreamInput {
  input: string;
  context?: Record<string, unknown>;
  options?: DreamOptions;
}

export interface DreamOptions {
  maxLevels?: number;
  confidenceThreshold?: number;
  includeRawData?: boolean;
}

export interface DreamResult {
  insights: Insight[];
  patterns: Pattern[];
  concepts: Concept[];
  hypotheses: Hypothesis[];
  metadata: DreamMetadata;
}

export interface Insight {
  id: string;
  content: string;
  confidence: number;
  novelty: number;
  sourceLevel: number;
  timestamp: Date;
}

export interface Pattern {
  id: string;
  type: string;
  description: string;
  confidence: number;
  occurrences: number;
}

export interface Concept {
  id: string;
  name: string;
  definition: string;
  relatedConcepts: string[];
}

export interface Hypothesis {
  id: string;
  statement: string;
  confidence: number;
  evidence: string[];
}

export interface DreamMetadata {
  processingTime: number;
  levelsProcessed: number;
  patternsFound: number;
  insightsGenerated: number;
}
