import {
  adfToText,
  doc,
  duplicateToAdf,
  paragraph,
  pirToAdf,
  rcaToAdf,
  text,
} from '../../src/lib/adf';
import { analysisFixture, duplicateFixture } from '../_fixtures';
import type { DuplicateResult } from '../../src/lib/contract';

describe('adf', () => {
  it('adfToText flattens nested text leaves depth-first', () => {
    const document = doc(paragraph(text('hello'), text('world')));

    const flattened = adfToText(document);

    expect(flattened).toContain('hello');
    expect(flattened).toContain('world');
  });

  it('adfToText returns empty string for non-ADF input', () => {
    expect(adfToText(null)).toBe('');
    expect(adfToText(42)).toBe('');
  });

  it('rcaToAdf renders a doc that surfaces severity and evidence', () => {
    const document = rcaToAdf(analysisFixture);

    expect(document.type).toBe('doc');
    const flattened = adfToText(document);
    expect(flattened).toContain('high');
    expect(flattened).toContain('INC-1');
  });

  it('pirToAdf renders a doc titled with the incident key', () => {
    const document = pirToAdf('AO-1', analysisFixture);

    expect(adfToText(document)).toContain('AO-1');
  });

  it('duplicateToAdf shows the polite explanation and link when confident', () => {
    const flattened = adfToText(duplicateToAdf(duplicateFixture));

    expect(flattened).toContain('Linked to INC-1');
    expect(flattened).toContain(duplicateFixture.verdict.explanation);
  });

  it('duplicateToAdf surfaces candidates for review when not confident', () => {
    const flagged: DuplicateResult = {
      ...duplicateFixture,
      flag_for_human: true,
      verdict: { ...duplicateFixture.verdict, candidates: ['INC-2', 'INC-3'] },
    };

    const flattened = adfToText(duplicateToAdf(flagged));

    expect(flattened).toContain('needs human review');
    expect(flattened).toContain('INC-2');
    expect(flattened).toContain('INC-3');
  });

  it('duplicateToAdf falls back to similar hits when candidates are empty', () => {
    const flagged: DuplicateResult = {
      ...duplicateFixture,
      flag_for_human: true,
      verdict: { ...duplicateFixture.verdict, candidates: [] },
    };

    const flattened = adfToText(duplicateToAdf(flagged));

    expect(flattened).toContain('INC-1'); // from result.similar fallback
  });
});
