// Real-world Drizzle forms (mirrors VibraFlow): single quotes, multi-line method chains,
// the 3-arg pgTable(name, cols, (table) => extras) form, decimal(), and enums imported by name.
import { pgTable, uuid, varchar, decimal, timestamp, index, unique } from 'drizzle-orm/pg-core';
import { alertLevelEnum } from './enums.js';
import { projects } from './projects.js';

export const budgets = pgTable(
  'budgets',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    project_id: uuid('project_id')
      .notNull()
      .references(() => projects.id, { onDelete: 'cascade' }),
    allocated_usd: decimal('allocated_usd', { precision: 12, scale: 2 }).notNull().default('0'),
    spent_usd: decimal('spent_usd', { precision: 12, scale: 2 }).notNull().default('0'),
    alert_level: alertLevelEnum('alert_level').notNull().default('green'),
    created_at: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    idxBudgetsProject: index('idx_budgets_project').on(table.project_id),
  })
);
