// Layer 4a/4: client types — generated from contract.json; do not hand-edit shapes.
// Casing policy: snake_case mirrors the wire format (FastAPI default). An elected
// camelCase policy would need a serialization-alias decision carried by the contract.

export type UserRole = "admin" | "member";
export type TaskStatus = "todo" | "in_progress" | "done";

export interface User {
  id: string; // uuid
  email: string;
  display_name: string;
  role: UserRole;
  created_at: string; // ISO datetime
}

export interface UserCreate {
  email: string;
  display_name: string;
  role?: UserRole;
}

export interface Project {
  id: string; // uuid
  owner_id: string; // uuid
  name: string;
  description: string | null;
  is_archived: boolean;
  created_at: string; // ISO datetime
}

export interface ProjectCreate {
  owner_id: string; // uuid
  name: string;
  description?: string | null;
}

export interface Task {
  id: string; // uuid
  project_id: string; // uuid
  title: string;
  status: TaskStatus;
  priority: number;
  due_date: string | null; // ISO datetime
  assignee_id: string | null; // uuid
  metadata: Record<string, unknown> | null;
  created_at: string; // ISO datetime
}

export interface TaskCreate {
  project_id: string; // uuid
  title: string;
  status?: TaskStatus;
  priority?: number;
  due_date?: string | null;
  assignee_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface Comment {
  id: string; // uuid
  task_id: string; // uuid
  author_id: string; // uuid
  body: string;
  created_at: string; // ISO datetime
}

export interface CommentCreate {
  task_id: string; // uuid
  author_id: string; // uuid
  body: string;
}
