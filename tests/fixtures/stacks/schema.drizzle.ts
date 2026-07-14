import { pgTable, pgEnum, uuid, varchar, text, boolean, integer, timestamp, jsonb } from "drizzle-orm/pg-core";

export const userRole = pgEnum("user_role", ["admin", "member"]);
export const taskStatus = pgEnum("task_status", ["todo", "in_progress", "done"]);

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  display_name: varchar("display_name", { length: 80 }).notNull(),
  role: userRole("role").notNull().default("member"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const tasks = pgTable("tasks", {
  id: uuid("id").primaryKey().defaultRandom(),
  project_id: uuid("project_id").notNull().references(() => projects.id),
  title: varchar("title", { length: 200 }).notNull(),
  status: taskStatus("status").notNull().default("todo"),
  priority: integer("priority").notNull().default(0),
  due_date: timestamp("due_date", { withTimezone: true }),
  assignee_id: uuid("assignee_id").references(() => users.id),
  metadata: jsonb("metadata"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
