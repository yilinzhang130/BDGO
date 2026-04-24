export interface FieldRule {
  visible_when?: Record<string, string | number | boolean | (string | number | boolean)[]>;
}

// Values the user types / toggles. Matches what ReportFormStage emits:
// text inputs → string, numeric inputs → number, checkboxes → boolean.
export type FieldValue = string | number | boolean;

// Subset of JSON Schema we actually render. The server can return
// richer shapes (const, pattern, etc.) but the form stage ignores them.
export interface FieldSpec {
  type: "string" | "integer" | "number" | "boolean";
  description?: string;
  default?: FieldValue;
  enum?: string[];
}

export interface FormSchema {
  type: string;
  properties: Record<string, FieldSpec>;
  required?: string[];
}

export interface ReportService {
  slug: string;
  display_name: string;
  description: string;
  mode: "sync" | "async";
  estimated_seconds: number;
  input_schema: FormSchema;
  output_formats: string[];
  field_rules?: Record<string, FieldRule>;
}

export interface ReportStartInfo {
  task_id: string;
  slug: string;
  estimated_seconds: number;
  params: Record<string, FieldValue>;
}

export type ReportStage = "form" | "running" | "done" | "error";
