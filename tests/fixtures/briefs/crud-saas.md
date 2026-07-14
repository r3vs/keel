# Brief — a small team task tracker (CRUD SaaS)

Build a web app where a team creates projects and tracks tasks inside them. Users sign in,
create a project, add tasks with a status (todo / in progress / done) and an optional assignee,
and comment on tasks. Multi-user, one shared workspace for now.

- **Project type:** web SaaS (full catalog applies).
- **Must:** persist data; authenticated users; a task's status and assignee are editable.
- **Out of scope for v1:** billing, multi-workspace/tenancy, notifications, a mobile client.
- **Constraints:** the team knows Postgres and TypeScript; deploy to a container host.

Expected forge behavior: elect the domain (User/Project/Task/Comment) and persistence
(relational Postgres) first; choose a shared-types contract carrier (TS end-to-end); defer
billing/tenancy as `deferred` pins rather than scaffolding them.
