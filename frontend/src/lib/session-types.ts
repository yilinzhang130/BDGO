// All shared TypeScript types for the chat session store.
// Imported by sessions.ts (store logic) and any component that needs
// type-only imports without pulling in store side-effects.

export type Role = "user" | "assistant";

export interface ToolEvent {
  type: "tool_call" | "tool_result";
  name: string;
}

export interface ReportTask {
  task_id: string;
  slug: string;
  estimated_seconds: number;
}

export interface PlanStep {
  id: string;
  title: string;
  description: string;
  tools_expected: string[];
  required: boolean;
  default_selected: boolean;
  estimated_seconds: number;
}

export interface PlanProposal {
  plan_id: string;
  title: string;
  summary: string;
  steps: PlanStep[];
}

export type PlanStatus = "pending" | "confirmed" | "cancelled";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  tools?: ToolEvent[];
  attachments?: string[];
  reportTasks?: ReportTask[];
  plan?: PlanProposal;
  planStatus?: PlanStatus;
  planSelectedIds?: string[]; // remembers which steps were ticked on confirm
  originalMessage?: string;   // original user prompt when plan was generated
  streaming?: boolean;
  createdAt: number;
}

export type EntityType =
  | "company"
  | "asset"
  | "clinical"
  | "deal"
  | "patent"
  | "buyer";

export interface ContextEntity {
  id: string; // dedupe key: `${entity_type}:${slug}`
  entityType: EntityType;
  title: string;
  subtitle?: string;
  fields: { label: string; value: string }[];
  href?: string;
  addedAt: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  contextEntities: ContextEntity[];
}
