-- Layer 1/4: DDL migration — generated from contract.json; do not hand-edit shapes.
BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE user_role AS ENUM ('admin', 'member');
CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done');

CREATE TABLE users (
    id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    email        varchar(255) NOT NULL UNIQUE,
    display_name varchar(80)  NOT NULL,
    role         user_role    NOT NULL DEFAULT 'member',
    created_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    uuid         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        varchar(120) NOT NULL,
    description text,
    is_archived boolean      NOT NULL DEFAULT false,
    created_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       varchar(200) NOT NULL,
    status      task_status  NOT NULL DEFAULT 'todo',
    priority    integer      NOT NULL DEFAULT 0,
    due_date    timestamptz,
    assignee_id uuid         REFERENCES users(id) ON DELETE SET NULL,
    metadata    jsonb,
    created_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX tasks_project_id_idx  ON tasks (project_id);
CREATE INDEX tasks_assignee_id_idx ON tasks (assignee_id);

CREATE TABLE comments (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id    uuid        NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id  uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX comments_task_id_idx ON comments (task_id);

COMMIT;
