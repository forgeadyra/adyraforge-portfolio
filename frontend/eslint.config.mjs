// eslint-config-next is intentionally not used: its fast-glob -> micromatch ->
// braces chain carries an unpatched high-severity advisory (GHSA-vfj7-8cjw-p6xm).
import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  jsxA11y.flatConfigs.recommended,
  reactHooks.configs.flat["recommended-latest"],
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "localStorage", message: "No auth state in localStorage (CLAUDE.md rule 4)." },
      ],
    },
  },
  prettier,
);
