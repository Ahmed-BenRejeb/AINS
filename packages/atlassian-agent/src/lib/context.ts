/** Invocation-context helpers for Rovo agent action handlers. */

/** The slice of a Forge action invocation context the actions rely on. */
export interface ActionContext {
  principal?: { accountId?: string };
}

/**
 * Resolve the invoking user's Atlassian account id from the action context.
 *
 * @param context - The Forge invocation context (may be undefined in tests).
 * @returns The account id, or `"unknown"` when it is not present.
 */
export function accountIdOf(context: ActionContext | undefined): string {
  return context?.principal?.accountId ?? 'unknown';
}
