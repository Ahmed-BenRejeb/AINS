import { adfToText, doc, paragraph, pirToAdf, rcaToAdf, text } from '../../src/lib/adf';
import { analysisFixture } from '../_fixtures';

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
});
