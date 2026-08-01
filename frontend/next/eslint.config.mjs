import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
    {
        ignores: [
            ".next/**",
            "coverage/**",
            "playwright-report/**",
            "test-results/**",
            "next-env.d.ts",
        ],
    },
    eslint.configs.recommended,
    ...tseslint.configs.strictTypeChecked.map((config) => ({
        ...config,
        files: ["**/*.{ts,tsx}"],
    })),
    {
        files: ["**/*.{ts,tsx}"],
        languageOptions: {
            parserOptions: {
                projectService: true,
                tsconfigRootDir: import.meta.dirname,
            },
        },
    },
);
