/**
 * Forge function entry points for the Sentinel Rovo agent.
 *
 * Each export is referenced by a `function` module in `forge.yml`
 * (`handler: index.<name>`) and backs one Rovo `action`.
 */

export { fetchIncident } from './actions/fetchIncident';
export { searchSimilarIncidents } from './actions/searchSimilarIncidents';
export { searchRunbooks } from './actions/searchRunbooks';
export { postRcaComment } from './actions/postRcaComment';
export { draftPirPage } from './actions/draftPirPage';
export { flagKnowledgeGap } from './actions/flagKnowledgeGap';
