# Brief — a URL-shortener API service

An HTTP API that creates short codes for URLs and redirects them. No UI — other services call it.
Track a hit count per short code.

- **Project type:** API service (prune client/rendering).
- **Must:** `POST /links` returns a short code; `GET /{code}` redirects and increments a counter;
  codes are stable and collision-free.
- **Out of scope for v1:** custom domains, analytics dashboards, auth/rate-limiting (note as a
  threat-model decision, deferred).
- **Constraints:** Postgres; a REST contract carried by OpenAPI; serverless deploy target.

Expected forge behavior: elect the domain (Link) + persistence + a REST/OpenAPI contract; the
threat model surfaces rate-limiting and abuse as security `open_decision`s (deferred with a
`flip_criteria`), not silently skipped.
