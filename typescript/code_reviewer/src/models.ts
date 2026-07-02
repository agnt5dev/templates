export type Severity = 'critical' | 'major' | 'minor' | 'nitpick';

export interface Finding {
  severity: Severity;
  category: string;
  description: string;
  line_reference: string;
  suggestion: string;
}

export interface FileReview {
  filename: string;
  language: string;
  findings: Finding[];
  summary: string;
}

export interface SecurityReview {
  findings: Finding[];
  overall_risk: string;
  summary: string;
}

export interface TechStack {
  languages: string[];
  frameworks: string[];
  test_files_present: boolean;
  config_files: string[];
  notes: string;
}

// JSON schemas for structured LM output (OpenAI strict mode compliant)
// ALL properties must be in required[], no defaults, no $ref with siblings
export const FINDING_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    severity: { type: 'string', enum: ['critical', 'major', 'minor', 'nitpick'] },
    category: { type: 'string', description: 'correctness, performance, quality, standards, or security' },
    description: { type: 'string' },
    line_reference: { type: 'string', description: "e.g. 'auth.py:45-52'. Empty string if not applicable." },
    suggestion: { type: 'string' },
  },
  required: ['severity', 'category', 'description', 'line_reference', 'suggestion'],
};

export const FILE_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    filename: { type: 'string' },
    language: { type: 'string' },
    findings: { type: 'array', items: FINDING_SCHEMA, description: 'Empty array if no issues.' },
    summary: { type: 'string' },
  },
  required: ['filename', 'language', 'findings', 'summary'],
};

export const SECURITY_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: { type: 'array', items: FINDING_SCHEMA, description: 'Empty array if no issues.' },
    overall_risk: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
    summary: { type: 'string' },
  },
  required: ['findings', 'overall_risk', 'summary'],
};
