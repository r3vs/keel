-- DB layer — drifts from contract.json ON PURPOSE (this is a rescue fixture).
BEGIN;

-- PLANTED DRIFT 1: enum is missing 'member' (contract has both admin + member)
CREATE TYPE user_role AS ENUM ('admin');

CREATE TABLE users (
    id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    email        varchar(255) NOT NULL UNIQUE,
    -- PLANTED DRIFT 2: display_name is nullable here; contract says NOT NULL
    display_name varchar(80),
    role         user_role    NOT NULL DEFAULT 'admin',
    created_at   timestamptz  NOT NULL DEFAULT now()
);

COMMIT;
