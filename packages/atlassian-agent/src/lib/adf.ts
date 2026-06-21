/**
 * Atlassian Document Format (ADF) builders and renderers.
 *
 * All Jira comments / issue descriptions and Confluence pages the agent writes
 * must be ADF — never plain strings or markdown (atlassian-agent CLAUDE.md). These
 * helpers build ADF nodes and render an {@link AnalyzeResult} into the documents
 * the actions post.
 */

import type { AnalyzeResult, DuplicateResult } from './contract';

/** A generic ADF node. */
export interface AdfNode {
  type: string;
  [key: string]: unknown;
}

/** The root ADF document node. */
export interface AdfDoc {
  type: 'doc';
  version: 1;
  content: AdfNode[];
}

/** An ADF text leaf. */
export function text(value: string): AdfNode {
  return { type: 'text', text: value };
}

/** An ADF paragraph wrapping the given inline nodes. */
export function paragraph(...content: AdfNode[]): AdfNode {
  return { type: 'paragraph', content };
}

/** An ADF heading at the given level. */
export function heading(level: number, value: string): AdfNode {
  return { type: 'heading', attrs: { level }, content: [text(value)] };
}

/** An ADF bullet list, one item per string. */
export function bulletList(items: string[]): AdfNode {
  return {
    type: 'bulletList',
    content: items.map((item) => ({
      type: 'listItem',
      content: [paragraph(text(item))],
    })),
  };
}

/** An ADF document wrapping the given block nodes. */
export function doc(...content: AdfNode[]): AdfDoc {
  return { type: 'doc', version: 1, content };
}

/**
 * Flatten an ADF node (or arbitrary JSON) into plain text.
 *
 * @param node - An ADF document, node, array of nodes, or leaf value.
 * @returns The concatenated text of every `text` leaf, depth-first.
 */
export function adfToText(node: unknown): string {
  if (Array.isArray(node)) {
    return node.map(adfToText).filter(Boolean).join(' ');
  }
  if (node !== null && typeof node === 'object') {
    const record = node as Record<string, unknown>;
    const parts: string[] = [];
    if (record.type === 'text' && typeof record.text === 'string') {
      parts.push(record.text);
    }
    if (Array.isArray(record.content)) {
      parts.push(adfToText(record.content));
    }
    return parts.filter(Boolean).join(' ');
  }
  return '';
}

/**
 * Render an analysis result as an RCA comment document.
 *
 * @param analysis - The backend `/analyze` result.
 * @returns An ADF doc summarising the RCA draft and its evidence.
 */
export function rcaToAdf(analysis: AnalyzeResult): AdfDoc {
  const rca = analysis.rca_draft;
  const confidencePct = (rca.confidence_score * 100).toFixed(0);
  const reviewNote = analysis.flag_for_human ? ' (flagged for human review)' : '';
  const content: AdfNode[] = [
    heading(3, 'Sentinel — Root Cause Analysis (draft)'),
    paragraph(text(`Root cause hypothesis: ${rca.root_cause_hypothesis}`)),
    paragraph(text(`Proposed severity: ${rca.proposed_severity} — ${rca.severity_rationale}`)),
    paragraph(text(`Suggested owner: ${rca.proposed_assignee_team}`)),
    paragraph(text(`Confidence: ${confidencePct}%${reviewNote}`)),
  ];
  if (rca.evidence.length > 0) {
    content.push(heading(4, 'Evidence'), bulletList(rca.evidence));
  }
  if (analysis.similar.length > 0) {
    content.push(
      heading(4, 'Similar past incidents'),
      bulletList(analysis.similar.map((hit) => `${hit.id} (score ${hit.score.toFixed(2)})`)),
    );
  }
  if (rca.duplicate_check.length > 0) {
    content.push(paragraph(text(`Possible duplicates: ${rca.duplicate_check.join(', ')}`)));
  }
  if (rca.knowledge_gaps.length > 0) {
    content.push(heading(4, 'Knowledge gaps'), bulletList(rca.knowledge_gaps));
  }
  return doc(...content);
}

/**
 * Render an analysis result as a post-incident-review page document.
 *
 * @param issueKey - The incident's Jira key (used in the page title/heading).
 * @param analysis - The backend `/analyze` result.
 * @returns An ADF doc for the PIR Confluence page.
 */
export function pirToAdf(issueKey: string, analysis: AnalyzeResult): AdfDoc {
  const rca = analysis.rca_draft;
  return doc(
    heading(2, `Post-Incident Review: ${issueKey}`),
    heading(3, 'Summary'),
    paragraph(text(rca.root_cause_hypothesis)),
    heading(3, 'Severity'),
    paragraph(text(`${rca.proposed_severity} — ${rca.severity_rationale}`)),
    heading(3, 'Evidence'),
    bulletList(rca.evidence.length > 0 ? rca.evidence : ['No supporting evidence retrieved.']),
    heading(3, 'Follow-up / knowledge gaps'),
    bulletList(rca.knowledge_gaps.length > 0 ? rca.knowledge_gaps : ['None identified.']),
  );
}

/**
 * Render a duplicate verdict as a Jira comment document.
 *
 * Has two branches: a confident, auto-linked duplicate posts the polite reporter
 * explanation; an uncertain verdict surfaces the rationale and candidate matches
 * for a human to review (graceful degradation).
 *
 * @param result - The backend `/duplicates` result.
 * @returns An ADF doc for the duplicate-check comment.
 */
export function duplicateToAdf(result: DuplicateResult): AdfDoc {
  const v = result.verdict;
  const confidencePct = (v.confidence * 100).toFixed(0);
  if (v.is_duplicate && !result.flag_for_human && v.duplicate_of) {
    return doc(
      heading(3, 'Sentinel — Possible Duplicate Detected'),
      paragraph(text(v.explanation)),
      paragraph(text(`Linked to ${v.duplicate_of} (confidence ${confidencePct}%).`)),
    );
  }
  const content: AdfNode[] = [
    heading(3, 'Sentinel — Duplicate Check (needs human review)'),
    paragraph(text(v.rationale)),
    paragraph(text(`Confidence ${confidencePct}% — below the auto-link threshold.`)),
  ];
  const candidates =
    v.candidates.length > 0
      ? v.candidates
      : result.similar.map((hit) => `${hit.id} (score ${hit.score.toFixed(2)})`);
  if (candidates.length > 0) {
    content.push(heading(4, 'Candidate matches'), bulletList(candidates));
  }
  return doc(...content);
}

/**
 * Render a knowledge-gap description document.
 *
 * @param topic - The topic with no matching runbook.
 * @param issueKey - The incident that surfaced the gap, if any.
 * @returns An ADF doc describing the gap.
 */
export function gapToAdf(topic: string, issueKey?: string): AdfDoc {
  const lead = issueKey ? `Surfaced while triaging ${issueKey}. ` : '';
  return doc(
    paragraph(
      text(
        `${lead}No runbook covers "${topic}". A runbook should be authored so future ` +
          'incidents on this topic can be resolved faster.',
      ),
    ),
  );
}
