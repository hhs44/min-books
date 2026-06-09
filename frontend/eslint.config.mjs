import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
    ],
  },
  {
    rules: {
      // The frontend integrates with a Pydantic backend; `any` is pragmatic
      // for free-form response shapes from cost/recent-calls/snapshots.
      "@typescript-eslint/no-explicit-any": "off",
      // Allow unescaped entities (apostrophes etc.) in Chinese strings
      "react/no-unescaped-entities": "off",
    },
  },
];

export default eslintConfig;