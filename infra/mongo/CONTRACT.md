# Smart Mirror — Data Contract (v0.1)

Shared agreement between the **dashboard** (writes) and the **mirror** (reads).
Enforced in code by `init_db.js` (Mongo `$jsonSchema` validators).
Change this file + `init_db.js` together, bump the version, tell both teams.

## Global rules

- Database: `ieee`. Content is **English only**.
- All dates are BSON `Date` in **UTC**. The mirror renders them in Africa/Tunis.
- Every write (insert/update) MUST set `updated_at` (now) and `updated_by` (board member username).
  Inserts also set `created_at`.
- `status`: `draft` | `published`. **Only `published` reaches the mirror.**
- Hard deletes are allowed (the mirror uses change streams + boot reconcile).
- Unknown extra fields are allowed but ignored by the mirror.
- Never rename or retype a field without a contract version bump.

## Common fields (every collection)

| field        | type                     | req |
|--------------|--------------------------|-----|
| `_id`        | ObjectId                 | auto |
| `status`     | `"draft"` \| `"published"` | yes |
| `created_at` | Date                     | yes |
| `updated_at` | Date                     | yes |
| `updated_by` | string                   | yes |

## Collections

### `events`
| field              | type          | req | notes |
|--------------------|---------------|-----|-------|
| `title`            | string        | yes | |
| `description`      | string        | yes | full text, goes to RAG |
| `start`            | Date          | yes | |
| `end`              | Date          | no  | |
| `location`         | string        | no  | |
| `tags`             | string[]      | no  | e.g. `["workshop","AI"]` |
| `registration_url` | string        | no  | |
| `image_url`        | string        | no  | poster |

### `announcements`
| field        | type                              | req | notes |
|--------------|-----------------------------------|-----|-------|
| `title`      | string                            | yes | |
| `body`       | string                            | yes | |
| `publish_at` | Date                              | yes | hidden before this |
| `expires_at` | Date                              | no  | hidden after this |
| `priority`   | `"low"` \| `"normal"` \| `"high"` | yes | |

### `about`
One document per section. `key` is unique.
| field   | type   | req | notes |
|---------|--------|-----|-------|
| `key`   | string | yes | `mission`, `history`, `contact`, … |
| `title` | string | yes | |
| `body`  | string | yes | |

### `achievements`
| field         | type   | req |
|---------------|--------|-----|
| `title`       | string | yes |
| `date`        | Date   | yes |
| `description` | string | yes |

### `board`
| field   | type   | req | notes |
|---------|--------|-----|-------|
| `name`  | string | yes | |
| `role`  | string | yes | e.g. `Chair` |
| `term`  | string | yes | e.g. `2026-2027` |
| `order` | int    | yes | display order |
| `email` | string | no  | public club contact only |

## Routing (what the mirror does with each collection)

| collection      | widget                                   | RAG | prompt block |
|-----------------|------------------------------------------|-----|--------------|
| `events`        | upcoming (`start >= now`), sorted        | yes | next 5 events |
| `announcements` | active (`publish_at <= now < expires_at`) | yes | active, `high` first |
| `about`         | —                                        | yes | `mission` only |
| `achievements`  | optional                                 | yes | — |
| `board`         | optional team page                       | yes | — |

Past events leave the widget but stay in RAG.
