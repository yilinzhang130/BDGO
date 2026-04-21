export interface FieldRule {
  visible_when?: Record<string, string | number | boolean | (string | number | boolean)[]>;
}

export interface ReportService {
  slug: string;
  display_name: string;
  description: string;
  mode: "sync" | "async";
  estimated_seconds: number;
  input_schema: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
  output_formats: string[];
  field_rules?: Record<string, FieldRule>;
}

export interface ReportStartInfo {
  task_id: string;
  slug: string;
  estimated_seconds: number;
  params: Record<string, any>;
}

export type ReportStage = "form" | "running" | "done" | "error";
