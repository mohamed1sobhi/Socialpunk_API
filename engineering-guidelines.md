# Engineering Guidelines — Vylo Social Media API

This document is the authoritative reference for architecture rules, coding constraints, and design contracts for this project. Every coding session must follow these rules without exception.

---

## 1. Module Internal Layer Rules

Every module under `app/modules/<module>/` must follow this strict internal layering:

| Layer | Responsibility | May Import From |
|---|---|---|
| `models/` | SQLAlchemy ORM entities | owning declarative base from `shared/database/base.py`, SQLAlchemy only |
| `repositories/` | All SQL operations | own `models/` only, SQLAlchemy types |
| `services/` | Pure business logic | `shared/auth/jwt.py`, `shared/events/bus.py`, `shared/events/events.py` (event class imports only) |
| `clients/` | Outbound adapters to other modules | own `schemas/public_schemas/responses.py` (boundary validation only) |
| `public/` | Inbound facade for other modules | own `schemas/public_schemas/requests.py` (boundary validation only) |
| `api/` | FastAPI routes, HTTP entry point | own `schemas/api_schemas.py`, `shared/auth/dependencies.py`, `shared/dependencies/<module>_deps.py` |

**No layer imports another layer of the same module** (e.g. `services/` must not import `repositories/`). All cross-layer coupling is delivered through `__init__` constructor injection, wired exclusively in `shared/dependencies/<module>_deps.py`.

---

## 2. Schema Layer Rules

| Schema File | Purpose | Used By |
|---|---|---|
| `schemas/api_schemas.py` | HTTP request/response Pydantic models | `api/` only |
| `schemas/public_schemas/requests.py` | Public-facade ingress validation models owned by the receiving domain | same domain `public/` only |
| `schemas/public_schemas/responses.py` | Client egress validation models owned by the consuming domain | same domain `clients/` only |

- `api_schemas` must **never** be used outside the `api/` layer.
- `public_schemas/requests.py` must **never** be imported outside its own module's `public/` layer.
- `public_schemas/responses.py` must **never** be imported outside its own module's `clients/` layer.
- No module may import another module's `schemas/public_schemas/*` files.
- `public_schemas.py`, `dto.py`, and `dtos.py` are forbidden for inter-module contracts.

---

## 3. Service Purity Contract

Services work exclusively with **pure Python types** (primitives, dataclasses, plain dicts). Neither Pydantic models nor SQLAlchemy ORM models may cross the service boundary in either direction.

- `api/` maps `api_schemas` → pure types → calls service → maps result back to `api_schemas`
- `public/` validates inbound inter-module payloads with own `schemas/public_schemas/requests.py` → converts to pure types → calls service → returns pure Python payloads
- `clients/` receives pure Python payloads from the foreign facade → validates them with own `schemas/public_schemas/responses.py` → converts to pure types → returns to own service
- All Pydantic validation for cross-module communication happens only at `public/` ingress and `clients/` egress.

---

## 4. Constructor-Based Dependency Injection Contract

All repositories, services, public facades, and clients use `__init__` constructor injection. No layer self-instantiates its own dependencies.

| Component | Injected With |
|---|---|
| `Repository` | `AsyncSession` |
| `Service` | own `Repository` instances + own `Client` instances |
| `Public facade` | own `Service` instance |
| `Outbound Client` | other module's `Public facade` instance |

All wiring is performed by FastAPI `Depends()` chains defined **exclusively** in `shared/dependencies/<module>_deps.py`. The `_deps.py` file is always the **last artifact** built in each phase.

---

## 5. Centralized Composition Root

`shared/dependencies/` is the **only** place where cross-module wiring occurs.

- Each module has exactly one corresponding `<module>_deps.py`.
- These files import concrete classes from modules and chain `Depends()` providers.
- A `_deps.py` may import another `_deps.py` to reuse an already-wired facade instance.
- Only `api/router.py` files and `main.py` (lifespan startup only) may import from `shared/dependencies/`.
- `services/`, `clients/`, and `public/` must **never** import from `shared/dependencies/`.

| File | Imports from |
|---|---|
| `users_deps.py` | `modules/users/*` only |
| `admins_deps.py` | `modules/admins/*` only |
| `social_graph_deps.py` | `modules/social_graph/*` + `users_deps` |
| `communities_deps.py` | `modules/communities/*` + `users_deps` |
| `content_deps.py` | `modules/content/*` + `communities_deps` |
| `notifications_deps.py` | `modules/notifications/*` + `communities_deps` + `users_deps` |

---

## 6. Communication Flow — The Single-Hop Rule

```
External request
      │
      ▼
Module A / api/              ← maps api_schema → pure type; calls injected Service
      │
      ▼
Module A / services/         ← pure logic; calls injected Client for cross-module needs
      │
      ▼
Module A / clients/          ← calls injected B/public/ facade; validates returned pure payload with own responses.py; returns pure type
      │
      ▼
Module B / public/           ← validates inbound payload with own requests.py; calls injected Service; returns pure Python payload
      │
      ▼
Module B / services/         ← pure logic
```

Cross-module calls are always exactly **one hop**: `clients/` → `public/`. Chaining public facades is forbidden.

---

## Frontend API Ownership Boundaries

From the frontend perspective, each module API owns a distinct responsibility boundary:

- `users/api/` owns non-system user registration, login, refresh-token flows, and user CRUD/profile operations.
- `admins/api/` owns system-user CRUD, system-user login, refresh-token flows, and all system role/permission assignment or revocation flows.
- Non-system users authenticate through `users/api/`, and their access and refresh tokens omit `system_permissions`.
- System users authenticate through `admins/api/`, and their access tokens carry `system_permissions` resolved from the admins module's role/permission model.
- Both login surfaces must issue the same HTTP token-pair envelope so the shared auth dependencies continue to work unchanged.
- `communities/api/` owns community lifecycle and membership workflows. If it needs to validate a user ID or fetch user data, it does so through its injected `UsersClient` calling the `users/public/` facade.
- Communities roles and permissions are global reference data. `communities/api/` may list them and assign seeded roles to members after tenant membership is validated, but it may not create or mutate the default catalog.
- `content/api/` owns community-scoped posts. Every post requires a community, and post read access derives from that community's visibility and the requester's membership rather than a post-level visibility field.
- Generic authenticated routes use `get_current_user` and then defer ownership, visibility, or membership checks to the owning domain service. Community-scoped content access is orchestrated by the content module using the communities module's access decisions, not by shared auth helpers.

---

## 7. Strict Prohibitions

```
❌ Any layer           →  imports another layer of the same module (outside the allowed list in §1)
❌ Any layer           →  imports anything from another module directly
❌ Any layer           →  imports another module's `schemas/public_schemas/*`
❌ api/                →  imports other module's public/ or api/
❌ public/             →  imports other module's public/ (no chaining)
❌ services/           →  imports repositories/, models/, api_schemas, public_schemas, or any other module
❌ services/           →  imports shared/dependencies/
❌ clients/            →  imports other module's services/, repositories/, models/, or schemas/
❌ handlers/           →  imports other module's public/, services/, repositories/, or models/
❌ shared/auth/dependencies.py → imports any module
❌ Any layer           →  uses `public_schemas.py`, `dto.py`, or `dtos.py` for inter-module boundaries
❌ users/api           →  owns system-user, system-role, or system-permission routes
❌ admins/api          →  owns non-system user registration, profile, or CRUD routes

✅ services/           →  shared/auth/jwt.py              (token issuance + password hashing)
✅ services/           →  shared/events/bus.py             (event publishing only)
✅ services/           →  shared/events/events.py          (event class imports for publishing)
✅ models/             →  shared/database/base.py          (owning schema base)
✅ repositories/       →  own models/                      (only this layer)
✅ clients/            →  own `schemas/public_schemas/responses.py` (boundary validation only)
✅ public/             →  own `schemas/public_schemas/requests.py`  (boundary validation only)
✅ api/                →  shared/auth/dependencies.py      (get_current_user, require_system_permission)
✅ api/                →  shared/dependencies/<module>_deps.py
✅ main.py (lifespan)  →  shared/dependencies/<module>_deps.py  (startup wiring only)
✅ _deps.py            →  own module's concrete classes + other _deps.py files
```

---

## 8. Authentication Contract

### Token Issuance — owned by `users/services/` and `admins/services/`

- `UserService` owns registration, login, access-token issuance, and refresh flows for non-system users stored in `users.users`.
- `AdminService` owns system-user CRUD, login, access-token issuance, refresh flows, and role/permission management for system users stored in `admins.users`.
- `UserService` does **not** manage system users, system roles, or system permissions.
- `AdminService` does **not** call the users module for system-user lifecycle or system-user login.
- Both services must issue the same HTTP token-pair envelope so `get_current_user` and `require_system_permission(...)` continue to work unchanged.

### JWT Encoding Rules

- `shared/auth/jwt.py` is pure functions only: zero DB calls, zero module imports.
- Validate the input schema before encoding. No payload normalization is allowed except `UUID` → `str` conversion.
- Keep token builders separate: `create_access_token(...)` and `create_refresh_token(...)`.
- Every encoded token must include `iat`, `exp`, and `jti`.
- Access tokens must include at least:
      - `sub` — the user ID as a string
      - `token_type="access"`
- Access tokens may include `system_permissions: list[str]`; absence means the subject has no system permissions.
- Refresh tokens must include at least:
      - `sub`
      - `token_type="refresh"`
- Non-system user access and refresh tokens must omit `system_permissions`.
- System users must receive `system_permissions` derived from the admins module's role/permission assignments.
- Refresh tokens must omit `system_permissions` because permissions are resolved again when an access token is issued.

### JWT Decoding Rules

- `decode_token()` verifies signature and expiration only.
- `decode_token()` returns the decoded payload `dict`.
- `decode_token()` must **not** enforce business rules such as token type, ownership, membership, or permissions.

### Auth FastAPI Dependency Contract

- `shared/auth/dependencies.py` has **zero imports from any module or `shared/dependencies/`**.
- `get_current_user` is the generic authenticated-route dependency:
      - extract the Bearer token with `OAuth2PasswordBearer`
      - call `decode_token()`
      - validate required claims: `sub`, `token_type`
      - enforce `token_type == "access"`
      - return the raw claims `dict`
- `require_system_permission(codename)` is the system-route dependency:
      - depend on `get_current_user`
      - read `current_user.get("system_permissions", [])`
      - raise `ForbiddenError` when the permission is absent
- The shared dependency layer is population-agnostic: it validates token claims only and does not care whether `sub` belongs to `users.users` or `admins.users`.
- Generic authenticated routes use `get_current_user` only. Ownership, membership, visibility, and similar business rules are then evaluated manually by the owning route/service pair.
- Shared auth helpers must not evaluate community-scoped content access, community membership, resource ownership, or any other domain rule.

### OAuth2 Login Input Contract

- Both `users/api/` and `admins/api/` login endpoints must use FastAPI `OAuth2PasswordRequestForm` as the input form contract.

### Request-Time Authorization Boundary

- **No DB call is made at request time to resolve system permissions.** System-permission checks rely only on access-token claims.
- Domain ownership and visibility checks are still allowed at request time, but they must happen inside the owning domain boundary. Until database RLS becomes authoritative, content services enforce post access using visibility and membership decisions supplied through the communities module's public boundary.
- `sub` must be resolved inside the owning domain boundary. A system-user token does not imply a matching row in `users.users`, and a non-system-user token does not imply a matching row in `admins.users`.

---

## 9. Layer Build Order

Within every module phase, always build in this order:

```
models → repositories → services → clients → public → schemas → api
→ shared/dependencies/<module>_deps.py
```

The `_deps.py` file is always the **last artifact** in each phase. It is the composition step that wires everything together.

---

## 10. Cross-Module Dependency Graph

```
users           ← no outbound module dependencies
admins          ← no outbound module dependencies
social_graph    → users
communities     → users
content         → communities
notifications   → communities, users
```

No module may introduce a dependency not listed in this graph.

---

## 11. Database And Migrations

- Each PostgreSQL schema has its own declarative base in `app/shared/database/base.py`; that base defines its schema through `MetaData(schema=...)`.
- Model classes inherit their owning schema base and must not repeat schema names in `__table_args__` or schema-qualify in-schema foreign-key targets.
- Cross-schema references are soft references: UUID columns or UUID plus owning-scope fields, without hard foreign-key constraints.
- `content.posts.community_id` is a required soft reference. Posts have no independent visibility column; public/private read access derives from the referenced community.
- Hard foreign keys are only for tables inside the same PostgreSQL schema.
- Alembic migrations define schema only. Seed rows, dummy data, role matrices, bootstrap users, and sample records are forbidden in migrations and runtime app code.
- Alembic uses the synchronous `MIGRATION_DATABASE_URL` loaded from `.env` through `shared/config/settings.py`.
- `alembic/env.py` imports `app/modules/model_registry.py`, then imports every listed model module dynamically so `ALL_METADATA` is populated.
- All migration revisions live together in `alembic/versions/`; per-schema revision directories are forbidden.
- Before online upgrades, `alembic/env.py` creates every known PostgreSQL schema and validates that metadata contains no cross-schema foreign keys.
- `social_graph.friend_requests` keeps directional `requester_id`/`receiver_id` semantics. PostgreSQL must prevent duplicate or reverse-duplicate pending requests with a partial unique index on `LEAST(requester_id, receiver_id), GREATEST(requester_id, receiver_id)` filtered to `status='pending'`.
- `social_graph.friendships` stores accepted friendships exactly once per unordered pair using canonical `user_low=min(user_a, user_b)` and `user_high=max(user_a, user_b)`. Enforce `UNIQUE(user_low, user_high)`, `CHECK(user_low < user_high)`, and indexes on both columns.
- Accepting a friend request must create one `social_graph.friendships` row and delete the request row. Bidirectional duplicate friendship rows are forbidden.
- `admins.user_roles.user_id` is an in-schema foreign key to `admins.users.id` because both tables live inside the `admins` schema.
- `get_db()` must use the following session atomicity guard:

```python
async with AsyncSessionLocal() as session:
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

---

## 12. Event Bus Rules

- `shared/events/base.py` defines `DomainEvent` (dataclass: `event_id: UUID`, `occurred_at: datetime` UTC).
- `shared/events/bus.py` implements the singleton `EventBus` using an `@subscribe` async decorator pattern; `bus.publish(event)` fans out to all registered handlers via `asyncio.gather`.
- **Event contracts** (e.g. `UserRegisteredEvent`, `FriendRequestSentEvent`) are defined in `shared/events/events.py`. These are the only shared objects that cross the publisher/subscriber boundary — they must never carry ORM models or Pydantic schemas.
- Module services that publish events import their event class from `shared/events/events.py` and call `await bus.publish(event)`.
- **Handler registration** is performed inside `NotificationService._setup_event_listeners()` using the `@event_bus.subscribe(EventClass)` decorator. This method is called once during `NotificationService.__init__`. The `NotificationService` is instantiated as a startup singleton via `notifications_deps.py` — not re-created per request.
- Handler methods live inside `NotificationService` and receive all required infrastructure and outbound clients via the service's `__init__` constructor — no self-instantiation, no module imports.
- Handlers must convert `DomainEvent` data into pure Python types before calling repository methods or passing data to delivery infrastructure.
- The event bus is used **only for notification triggers** — it must not replace the `clients/` → `public/` communication pattern for data flow.
- Services import the bus as `from app.shared.events.bus import bus`; event types are imported as `from app.shared.events.events import <EventClass>`.

---

## 13. Shared Infrastructure Rules

| Component | File | Rule |
|---|---|---|
| Settings | `shared/config/settings.py` | Single `BaseSettings` instance; all config from environment variables |
| Database metadata | `shared/database/base.py` | One declarative base per PostgreSQL schema; exports `ALL_METADATA` for Alembic |
| Database session | `shared/database/session.py` | Async engine only (`create_async_engine`); `get_db` yields `AsyncSession` with atomicity guard |
| JWT + hashing | `shared/auth/jwt.py` | Pure functions only — zero DB access, zero module imports |
| Auth dependencies | `shared/auth/dependencies.py` | Zero module imports; decodes tokens, validates required claims, and exposes `require_system_permission()` over `get_current_user()` for both non-system and system-user tokens |
| WebSocket manager | `shared/websockets/manager.py` | Module-level singleton; injected into `NotificationService` via constructor DI |
| Exception handlers | `shared/exceptions/handlers.py` | Covers `HTTPException`, `RequestValidationError`, unhandled 500 |
| Composition roots | `shared/dependencies/<module>_deps.py` | One file per module; the only place cross-module wiring happens |

---

## Default Data Seeding Rule

- No module may insert bootstrap data, default roles, default permissions, or other reference rows in migrations, request handling, service construction, app startup, or shared dependency wiring.
- All default/reference data must be created explicitly in `scripts/seed_<module_name>.py`.
- Seed scripts own their own `AsyncSessionLocal` lifecycle, perform explicit commit/rollback, close the session in `finally`, and dispose the engine before exiting.
- `main.py`, service constructors, and request handlers must never invoke seeding logic implicitly.
- If a module requires initial data such as system roles/permissions, that requirement must be documented beside a corresponding seed script rather than implemented as hidden startup behavior.
- Communities role and permission reference rows are seeded only by `scripts/seed_communities.py`; runtime code may list and assign them, but it must not create or mutate the default catalog.

---

## 14. Notification Service Zero-Import Rule

`NotificationService` must have **zero cross-module imports**. Its constructor receives all required dependencies via injection:

**Infrastructure dependencies:**
- `NotificationRepository`
- `InMemoryConnectionManager` (WebSocket delivery)
- `EmailClient` (email delivery)
- `TwilioSMSClient` (SMS delivery)

**Outbound clients (for cross-module reads inside handlers):**
- `UsersClient` (e.g. resolve a user's email address or phone number)
- `CommunitiesClient` (e.g. resolve community owner/member list for fan-out)

All cross-module lookups are performed by calling methods on these injected client instances. Clients receive their foreign facade via `__init__` injection, validate returned payloads with their own `schemas/public_schemas/responses.py`, and never import another module's schemas at any level.

Handler methods live inside `NotificationService` and are registered via `@event_bus.subscribe` inside `_setup_event_listeners()`. Each handler: persists a DB notification row, broadcasts via `InMemoryConnectionManager`, and triggers `EmailClient`/`TwilioSMSClient` as required by the event type. Handlers must convert `DomainEvent` data to pure Python types before calling repository methods or delivery infrastructure.
