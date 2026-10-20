/**
 * Configuração do ESLint.
 *
 * O script `lint` roda com `--max-warnings 0` de propósito: um lint que
 * devolve exit 0 **com** warnings dá falsa sensação de aprovado, e muitos CIs
 * de build tratam warning como erro — um só derruba o deploy. Aqui o
 * warning falha localmente, antes de chegar lá.
 *
 * As regras extras abaixo são as que importam num cofre de senhas: nada de
 * `console` deixando rastro no navegador de quem usa, nada de `any` abrindo
 * buraco no tipo de uma resposta que carrega segredo.
 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  plugins: ['@typescript-eslint', 'react-hooks'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '*.cjs', 'vite.config.ts'],
  rules: {
    // Variável não usada vira erro, mas `_` prefixado é intenção explícita.
    '@typescript-eslint/no-unused-vars': [
      'error',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
    ],
    // Num cofre, um console.log esquecido pode imprimir o que foi revelado.
    'no-console': 'error',
    // alert/confirm travam a aba e não dá para estilizar o aviso.
    'no-alert': 'error',
    '@typescript-eslint/no-explicit-any': 'error',
  },
}
