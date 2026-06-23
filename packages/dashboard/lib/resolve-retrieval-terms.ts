import conceptDimensionMap from "./dimension_labels.json";

export type ConceptDimensionMap = Record<string, number[]>;

const inverted = buildInvertedIndex(conceptDimensionMap as ConceptDimensionMap);

/** Build dim id → concept labels from the interpretability pipeline output. */
function buildInvertedIndex(map: ConceptDimensionMap): Map<number, string[]> {
  const index = new Map<number, string[]>();
  for (const [label, dims] of Object.entries(map)) {
    for (const dim of dims) {
      const existing = index.get(dim) ?? [];
      existing.push(label);
      index.set(dim, existing);
    }
  }
  return index;
}

export interface ResolvedRetrievalAttribution {
  terms: Record<string, number>;
  unmappedDims: string[];
}

/**
 * Map xqdrant dimension contributions to SRE concept labels.
 * Used when trace metadata has raw ``dims`` only (older runs / mock fallback).
 */
export function resolveRetrievalTerms(
  dims: Record<string, number>,
): ResolvedRetrievalAttribution {
  const terms: Record<string, number> = {};
  const unmappedDims: string[] = [];

  for (const [dimStr, contribution] of Object.entries(dims)) {
    const dimId = Number.parseInt(dimStr, 10);
    if (Number.isNaN(dimId)) {
      unmappedDims.push(dimStr);
      continue;
    }
    const labels = inverted.get(dimId) ?? [];
    if (labels.length === 0) {
      unmappedDims.push(dimStr);
      continue;
    }
    const share = contribution / labels.length;
    for (const label of labels) {
      terms[label] = (terms[label] ?? 0) + share;
    }
  }

  return { terms, unmappedDims };
}

/** Sort concept contributions for display (descending). */
export function sortedTermEntries(terms: Record<string, number>): [string, number][] {
  return Object.entries(terms).sort(([, a], [, b]) => Math.abs(b) - Math.abs(a));
}
