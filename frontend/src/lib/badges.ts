export function phaseBadgeClass(phase: string): string {
  if (!phase) return "badge-gray";
  const p = phase.toLowerCase();
  if (p.includes("approved") || p.includes("上市")) return "badge-green";
  if (p.includes("3")) return "badge-blue";
  if (p.includes("2")) return "badge-purple";
  if (p.includes("1")) return "badge-amber";
  if (p.includes("pre")) return "badge-gray";
  return "badge-gray";
}

export function priorityBadgeClass(priority: string): string {
  if (!priority) return "badge-gray";
  if (priority === "A") return "badge-green";
  if (priority === "B") return "badge-blue";
  return "badge-gray";
}

export function resultBadgeClass(result: string): string {
  if (!result) return "badge-gray";
  if (result.includes("积极") || result.includes("positive")) return "badge-green";
  if (result.includes("阴性") || result.includes("negative") || result.includes("未达成"))
    return "badge-red";
  if (result.includes("混合")) return "badge-amber";
  return "badge-gray";
}

export function statusBadgeClass(status: string): string {
  if (status === "有效") return "badge-green";
  if (status === "已过期") return "badge-red";
  return "badge-gray";
}
