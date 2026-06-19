/** Jest config — ts-jest, Node env, tests + the @forge/api manual mock live under tests/. */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  // roots = tests/ so the manual mock at tests/__mocks__/@forge/api.ts is the
  // "adjacent to node_modules" location Jest auto-applies for that module.
  roots: ['<rootDir>/tests'],
  moduleFileExtensions: ['ts', 'js', 'json'],
  clearMocks: true,
};
