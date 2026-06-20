import next from "eslint-config-next";

// Next 16 removed `next lint` and ships a native ESLint 9 flat config.
// `eslint-config-next` (default export) bundles core-web-vitals + the TS rules.
const eslintConfig = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...next,
];

export default eslintConfig;
