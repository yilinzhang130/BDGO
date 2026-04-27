"use client";

import { TabComingSoon } from "../_components/TabComingSoon";

export default function BuyersTabPage() {
  return (
    <TabComingSoon
      tab="Buyers"
      pr="P2-3"
      what="替代 /buyers slash — 用资产参数自动填表，一键反向匹配 Top-N 买方，结果直接落到这里。"
      bullets={[
        "表单：target / indication / phase / top_n / 偏好（按 deal_size / 治疗领域 / 地区）",
        "自动用资产 metadata 预填",
        "结果 table：买方公司 + 匹配理由 + 历史 deal",
        '操作按钮："加入 outreach 列表" / "为这家生成 teaser"',
      ]}
    />
  );
}
