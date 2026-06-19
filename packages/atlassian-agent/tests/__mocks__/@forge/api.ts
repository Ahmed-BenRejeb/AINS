/**
 * Manual Jest mock for `@forge/api`.
 *
 * Auto-applied for every test under `tests/` (Jest treats this `__mocks__`
 * folder as adjacent to node_modules for that module). Tests configure the
 * exported `jest.fn()`s — `requestJira`, `requestConfluence`, `fetch` — and read
 * their `.mock.calls`. `route` is a plain template-tag that concatenates its
 * parts so URL assertions stay readable.
 */

export const requestJira = jest.fn();
export const requestConfluence = jest.fn();
export const fetch = jest.fn();

export const route = (strings: TemplateStringsArray, ...values: unknown[]): string =>
  strings.reduce(
    (acc, part, index) => acc + part + (index < values.length ? String(values[index]) : ''),
    '',
  );

const productMethods = { requestJira, requestConfluence };

const api = {
  asApp: () => productMethods,
  asUser: () => productMethods,
};

export default api;
