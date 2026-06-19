/* ESLint (flat config not used — classic config for eslint 8 + typescript-eslint). */
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 2020, sourceType: 'module' },
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  env: { node: true, es2020: true },
  ignorePatterns: ['dist/', 'node_modules/', 'jest.config.js', '.eslintrc.cjs'],
  overrides: [{ files: ['tests/**/*.ts'], env: { jest: true } }],
};
