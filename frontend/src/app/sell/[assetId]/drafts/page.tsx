"use client";

import { TabComingSoon } from "../_components/TabComingSoon";

export default function DraftsTabPage() {
  return (
    <TabComingSoon
      tab="Drafts"
      pr="P2-7"
      what="替代 5 个 /draft-* slash — 把 prompt 拼接升级为参数表单。"
      bullets={[
        "顶部选 draft 类型 (TS / MTA / License / Co-Dev / SPA)",
        "每种 draft 一个表单 (upfront / milestone / royalty / territory / field / term...)",
        "结果：markdown preview + 下载 .docx + 改参数重新生成",
        "版本历史侧栏：v1 / v2 / v3...",
      ]}
    />
  );
}
