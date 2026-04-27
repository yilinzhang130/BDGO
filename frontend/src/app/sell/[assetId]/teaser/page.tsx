"use client";

import { TabComingSoon } from "../_components/TabComingSoon";

export default function TeaserTabPage() {
  return (
    <TabComingSoon
      tab="Teaser"
      pr="P2-4"
      what="替代 /teaser slash — 表单生成 + 按 buyer 定制变体（解决 S2-02：同一份 teaser 发不同 buyer）。"
      bullets={[
        "表单：受众类型 (MNC / mid-pharma / VC) + 强调点 + 语言 + 长度",
        "结果：markdown preview + 下载 .docx + 下载 .pptx",
        '"按 buyer 定制" 区：选已 match 的 buyer → 个性化变体',
        "历史变体列表（哪 buyer 看的哪版）",
      ]}
    />
  );
}
