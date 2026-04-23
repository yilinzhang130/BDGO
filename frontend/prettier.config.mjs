// prettier.config.mjs — Prettier 格式化配置
//
// CI 会跑:  npx prettier --check .  (只验证,不改)
// 本地想自动格式化:  npx prettier --write .

export default {
  semi: true,
  singleQuote: false,
  trailingComma: "all",
  printWidth: 100,
  tabWidth: 2,
  arrowParens: "always",
};
