"use client";

import { TabComingSoon } from "../_components/TabComingSoon";

export default function DataroomTabPage() {
  return (
    <TabComingSoon
      tab="Dataroom"
      pr="P2-6"
      what="把 /dataroom 的 markdown 输出升级为可勾选 checklist + 文件占位。"
      bullets={[
        "生成清单 → 分类 (Clinical / CMC / IP / Reg / Quality / Commercial / Financial)",
        "每条 = 文件名 + checkbox + 上传文件占位 + 备注",
        "状态持久化（新表 dataroom_items）",
        '"数据室就绪审计" 一键统计已准备 / 未准备 / 关键缺失',
      ]}
    />
  );
}
