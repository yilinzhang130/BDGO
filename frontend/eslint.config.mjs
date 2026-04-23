// eslint.config.mjs — 前端 ESLint flat config (ESLint 9+)
//
// 扫描 Next.js / React / TypeScript 代码。CI 会跑:
//   npx eslint .
//
// 本地想自动修能修的问题:
//   npx eslint . --fix

import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default [
  // ESLint 官方推荐基础规则(未定义变量、未使用代码等真错类)
  js.configs.recommended,

  // TypeScript 规则集 —— 识别 TS 语法,提示类型相关问题
  ...tseslint.configs.recommended,

  // Next.js 官方规则 + React Hooks 规则
  {
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooks,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      ...reactHooks.configs.recommended.rules,
    },
  },

  // 项目风格类规则降级成 warning —— 会在 CI 里显示但不阻塞合并。
  // 现有代码里这几类问题数量较大,一次清完 PR 会太大;降 warn 让新代码
  // 触发时能看到提示,同时留出后续专项 PR 逐批清理的空间。
  // TODO: 清完存量后把下面这几条改回 "error"。
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": "warn",
      "no-empty": "warn",
      "@next/next/no-html-link-for-pages": "warn",
      "@next/next/no-img-element": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },

  // 放在最后 —— 关掉所有和 Prettier 冲突的格式类规则,交给 Prettier 管
  prettier,

  // 忽略构建产物 / 依赖
  {
    ignores: [".next/**", "node_modules/**", "public/**", "next-env.d.ts", "tsconfig.tsbuildinfo"],
  },
];
