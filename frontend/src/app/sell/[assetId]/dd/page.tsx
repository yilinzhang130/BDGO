"use client";

import { TabComingSoon } from "../_components/TabComingSoon";

export default function DdTabPage() {
  return (
    <TabComingSoon
      tab="DD"
      pr="P2-5"
      what="把 /dd seller + /faq + /meeting 三个 slash 整合为一条 DD 准备时间线。"
      bullets={[
        "时间线：CDA 准备 → 数据室开放 → 对方 DD 提问 → 面对面会议 → 出决定",
        "每里程碑一个功能卡：dd-checklist (seller) / FAQ 预生成 / meeting-brief",
        "每张卡可独立运行 + 结果留存",
        "导出 PDF / 复制到剪贴板",
      ]}
    />
  );
}
