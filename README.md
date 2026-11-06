# Socialpunk API

FastAPI / SQLAlchemy / PostgreSQL social-media API. Project engineering rules
are maintained in [engineering-guidelines.md](engineering-guidelines.md).

## Pagination

### Cursor endpoints

The following endpoints accept `limit` (default **50**, range **1–100**) and
optional `after`:

| Endpoint (under `/api/v1`) | Collection | Ordering |
|---|---|---|
| `GET /posts` | `posts` | `created_at DESC, id DESC` |
| `GET /users/{user_id}/posts` | `posts` | `created_at DESC, id DESC` |
| `GET /communities/{community_id}/posts` | `posts` | `created_at DESC, id DESC` |
| `GET /notifications` | `notifications` | `created_at DESC, id DESC` |
| `GET /communities` | `communities` | `created_at DESC, id DESC` |
| `GET /communities/{community_id}/members` | `members` | `joined_at ASC, id ASC` |
| `GET /social/friends` | `friend_ids` | friend UUID `ASC` |
| `GET /social/friends/requests/pending` | `requests` | `created_at DESC, id DESC` |

Existing audience and community-access checks still apply. Public community
discovery remains anonymous; post reads allow anonymous viewers or user tokens.

First page:

```http
GET /api/v1/posts?limit=50
```

Response:

```json
{
  "posts": [],
  "page_info": {
    "next_cursor": null,
    "has_more": false
  }
}
```

For a non-final page, `next_cursor` contains an opaque string. URL-encode it and
pass it as `after` to fetch the next page. Stop when `has_more` is false.
Resource identifiers such as `author_id`, `community_id`, and `user_id` remain
in the endpoints' existing response envelopes.

Cursors contain a version, resource/sort/viewer scope, and ordering values,
authenticated with a pagination-specific HMAC key derived from `SECRET_KEY`.
They preserve timestamp microseconds and do not require the anchor row to still
exist. Changing `SECRET_KEY` invalidates old cursors. Invalid, modified, or
cross-resource/viewer cursors return HTTP **422**.

These are live lists, not snapshots across requests. Refresh the first page to
see newly inserted newer posts/notifications. Membership and visibility are
reevaluated for every request, so access changes can affect later pages. A
cursor never grants access. UUID friendship ordering is stable, not alphabetical
or friendship-recency ordering.

**Frontend migration:** `offset` is removed from scrolling endpoints and is
rejected as an extra query parameter, including `offset=0`. Previously unbounded
lists now return at most 50 rows by default. Replace offset increments with
`page_info.next_cursor`. Exact totals and previous-page cursors are not returned.

### Administrative roles

`GET /api/v1/admins/roles` accepts `limit` (default 50, range 1–100) and
`offset` (default 0, nonnegative), ordered by unique role name ascending:

```json
{
  "roles": [],
  "page_info": {
    "limit": 50,
    "offset": 0,
    "next_offset": null,
    "has_more": false
  }
}
```

Use `next_offset` to continue or compute `(page_number - 1) * limit` for numbered
navigation. The fixed community role/permission catalogs remain unpaginated.

### Internal batching

`communities/public/CommunityFacade.list_member_ids()` accepts `limit`
(default 500, maximum 1000) and `after`, returning `member_ids` plus `page_info`.
The notifications client validates that contract; post notification fan-out
consumes every batch and excludes the author. Delivery is still sequential and
live membership changes can affect later batches. Batching bounds memory; it
does not turn fan-out into a background job or a snapshot of recipients.

The internal user-community list is also bounded with cursors, retaining its
existing community-creation-time ordering. The global feed still obtains the
complete accessible-community ID set before querying posts; independently
paginating that set would produce an incorrect globally ordered feed. The
unnecessary sort on that ID-set lookup has been removed, but enumerating a very
large access set remains a separate scaling concern.

## Database rollout

Revision `d7e9a102bc34` corrects pending-pair uniqueness and adds these indexes:

| Table | New index coverage |
|---|---|
| `content.posts` | Live-post community, author, and global chronological keysets |
| `notifications.notifications` | Recipient chronological keyset; unread recipient lookup |
| `communities.communities` | Public chronological discovery |
| `communities.community_members` | Community/join-time/member-ID keyset, including user ID |
| `social_graph.friend_requests` | Pending receiver chronological keyset |
| `social_graph.friendships` | Reverse canonical-pair traversal `(user_high, user_low)` |

The pending-pair expression index now filters on **`status = 'PENDING'`**,
matching SQLAlchemy's persisted enum names. API/service statuses remain
lowercase. Pair lookup uses the same `least` / `greatest` expressions as the
unique index. Existing single-column indexes are retained.

Run from the repository root using the configured environment:

```bash
.venv/bin/python -m scripts.inspect_pagination_data
```

This reports raw visibility/status counts and duplicate pending-pair counts.
If legacy `PUBLIC` / `PRIVATE` visibility rows exist, explicitly normalize them:

```bash
.venv/bin/python -m scripts.inspect_pagination_data --normalize-visibility
```

The repair changes only those uppercase visibility values and commits
transactionally; it inserts or deletes no rows. If duplicate pending pairs are
reported, resolve which requests to retain before upgrading. No request is
automatically deleted. Unexpected visibility values must also be resolved.

Then apply the schema migration before deploying the updated API:

```bash
.venv/bin/alembic upgrade head
```

The migration checks legacy visibility and duplicate pairs before changing
indexes, and fails with an actionable message rather than silently rewriting
data. Index builds are transactional, not concurrent; schedule the upgrade
appropriately for a busy populated database. Downgrade removes the new indexes
and restores the previous pending-pair predicate, so it also restores that
older revision's uniqueness defect. The visibility repair is not undone.

## Verification

Unit and HTTP-contract tests:

```bash
.venv/bin/python -m pytest -q
```

PostgreSQL integration tests are enabled by `TEST_DATABASE_URL`:

```bash
TEST_DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE" \
  .venv/bin/python -m pytest -q
```

The integration fixtures create uniquely named, transaction-local schemas and
roll back all tables/data at teardown. They require schema-creation privileges
but never read or modify application tables. The migration test renders and
executes every revision in isolated schemas, including legacy-data preflight,
upgrade, reverse-duplicate rejection, and downgrade. Behavioral tests cover
ties, deleted anchors, concurrent newer inserts, access revocation, recipient
scope, both friendship directions, and multi-batch notification fan-out.

Representative PostgreSQL query plans:

```bash
.venv/bin/python -m scripts.benchmark_pagination --rows 100000
.venv/bin/python -m scripts.benchmark_pagination --rows 100000 --full-plans
```

The benchmark uses `DATABASE_URL`, captures actual repository queries, and
executes `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` against isolated synthetic
data. It compares first-page, deep-cursor, and deep-offset reads for hot and
sparse tenants/users, including multi-community feeds. All schemas and data
are rolled back on completion or failure. Output includes index names, shared
blocks, examined scan rows (including filtered rows), and execution time;
`--full-plans` also includes complete plans. `--deep-offset` defaults to 50000
and is reduced to half the matching rows for smaller result sets.
The benchmark also checks expression-index pending-pair lookup and executes
the existing mark-all-read update on an isolated sparse recipient's unread rows.

An initial local run with 100,000 rows per growing table produced:

| Query | Deep offset | Offset time | Cursor time |
|---|---:|---:|---:|
| Broad post feed | 45,000 | 161.62 ms | 0.44 ms |
| Notification history | 40,000 | 135.96 ms | 0.45 ms |
| Community members | 40,500 | 135.44 ms | 0.47 ms |
| Pending requests | 34,286 | 109.95 ms | 0.47 ms |
| Friends | 50,000 | 500.69 ms | 0.93 ms |

These are single-run local measurements, not production latency guarantees.
The integration plan regression test checks index conditions and reduced scan
work/buffer usage rather than asserting machine-dependent timing thresholds.
