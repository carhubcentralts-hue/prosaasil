/** @type {import('eslint').Linter.Config} */
module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint', 'react-hooks', 'react-refresh'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '*.config.*', '*.cjs'],
  rules: {
    // React hooks correctness
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',

    // Fast-refresh compatibility
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

    // TypeScript — keep it practical for existing codebase
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/consistent-type-imports': ['warn', { prefer: 'type-imports', disallowTypeAnnotations: false }],

    // Downgrade pre-existing patterns to warn so CI is not blocked
    'no-case-declarations': 'warn',
    'no-empty-pattern': 'warn',
    'no-useless-catch': 'warn',

    // General
    'no-console': ['warn', { allow: ['warn', 'error', 'info'] }],
  },
};
