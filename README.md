# Stage 3: Insighta Labs+ Intelligence Platform

A production-ready demographic intelligence platform built with **FastAPI (for Backend)**, **PostgreSQL**, a standalone **CLI client** and **web portal (with React)**.

Insighta Labs+ aggregates demographic signals from external intelligence providers (**Genderize**, **Agify**, and **Nationalize**), persists normalized profile data, secures access with **GitHub OAuth + JWT**, and exposes multiple interfaces:

* REST API
* Natural language query engine
* CLI application
* CSV export system

---

# 🌟 Core Features

## Intelligence Engine

* Advanced profile filtering
* Combined conditional queries
* Sorting and pagination
* Natural language search parsing
* CSV export support

## Authentication & Security

* GitHub OAuth authentication with PKCE
* JWT access & refresh tokens
* Refresh token rotation
* Role-based access control (RBAC)
* Global API version enforcement
* Rate limiting
* Request logging

## Multi-Interface Access

* REST API
* Standalone CLI (`insighta`)
* CSV exports
* Shared authentication model across interfaces

---

# 🏗️ System Architecture

```text
                ┌────────────────────┐
                │   GitHub OAuth     │
                └─────────┬──────────┘
                          │
                    OAuth + PKCE
                          │
        ┌─────────────────▼─────────────────┐
        │          FastAPI Backend          │
        │-----------------------------------│
        │ Auth Layer (JWT + RBAC)           │
        │ Profile Intelligence Engine       │
        │ NLQ Parser                        │
        │ CSV Export Service                │
        │ Rate Limiting                     │
        │ Logging Middleware                │
        └─────────────────┬─────────────────┘
                          │
                    SQLAlchemy ORM
                          │
                ┌─────────▼─────────┐
                │   PostgreSQL DB   │
                └───────────────────┘
                          ▲
                          │
             ┌────────────┴────────────┐
             │                         │
      ┌──────▼──────┐         ┌────────▼────────┐
      │ CLI Client  │         │     Web UI      │
      └─────────────┘         └─────────────────┘
```

---

# 🔐 Authentication Flow

Insighta Labs+ uses **GitHub OAuth with PKCE** for secure authentication.

## OAuth Flow

### Step 1 — Login Request

```http
GET /auth/github
```

Backend:

* Generates PKCE verifier/challenge
* Stores verifier in session
* Redirects user to GitHub OAuth

---

### Step 2 — GitHub Callback

```http
GET /auth/github/callback
```

Backend:

* Exchanges authorization code
* Retrieves GitHub profile
* Creates or retrieves user
* Issues JWT tokens

Response:

```json
{
  "status": "success",
  "access_token": "jwt",
  "refresh_token": "jwt"
}
```

---

### Step 3 — Authenticated Requests

All protected endpoints require:

```http
Authorization: Bearer <access_token>
X-API-Version: 1
```

---

### Step 4 — Token Refresh

```http
POST /auth/refresh
```

Request:

```json
{
  "refresh_token": "jwt"
}
```

Behavior:

* Validates refresh token
* Revokes old token immediately
* Issues a new token pair

---

### Step 5 — Logout

```http
POST /auth/logout
```

Behavior:

* Revokes refresh token server-side

---

# 🔑 Token Handling Approach

## Access Tokens

* JWT-based
* Expiry: **3 minutes**
* Used for all API access

## Refresh Tokens

* Expiry: **5 minutes**
* Persisted in database
* Rotated on every refresh
* Old token invalidated immediately

---

## Refresh Token Rotation Logic

```text
Client sends refresh token
        ↓
Backend validates token
        ↓
Old refresh token revoked
        ↓
New access token issued
        ↓
New refresh token issued
```

This prevents replay attacks and stale session reuse.

---

# 👥 Role-Based Access Control (RBAC)

Two system roles exist:

| Role    | Permissions       |
| ------- | ----------------- |
| admin   | Full access       |
| analyst | Read/query access |

---

## Enforcement Logic

Protected dependencies:

```python
require_admin()
require_analyst()
```

### Example

```python
@router.delete("/{id}")
def delete_profile(
    user: User = Depends(require_admin)
):
```

Behavior:

* Analysts cannot delete profiles
* Inactive users receive `403 Forbidden`

---

# 📂 API Reference

---

# Authentication Endpoints

## GitHub Login

```http
GET /auth/github
```

Redirects to GitHub OAuth.

---

## OAuth Callback

```http
GET /auth/github/callback
```

Creates/retrieves user and issues tokens.

---

## Refresh Tokens

```http
POST /auth/refresh
```

---

## Logout

```http
POST /auth/logout
```

---

# Profile Endpoints

---

## Create Profile

```http
POST /api/profiles
```

Body:

```json
{
  "name": "Harriet Tubman"
}
```

Behavior:

* Concurrent upstream API aggregation
* Age classification
* Country inference
* Idempotent persistence

---

## Get Profile

```http
GET /api/profiles/{id}
```

---

## List Profiles

```http
GET /api/profiles
```

Supports:

* Filtering
* Sorting
* Pagination

---

## Natural Language Search

```http
GET /api/profiles/search?q=young males from nigeria
```

---

## Export CSV

```http
GET /api/profiles/export?format=csv
```

Returns:

```http
Content-Type: text/csv
Content-Disposition: attachment
```

---

# 🧠 Natural Language Parsing Approach

The query engine uses **rule-based parsing only**.

No AI models or LLMs are used.

---

## Parsing Pipeline

### 1. Gender Detection

```text
male, female
```

### 2. Age Logic

```text
young → age 16–24
above 30 → age > 30
under 18 → age < 18
```

### 3. Age Group Detection

```text
child
teenager
adult
senior
```

### 4. Country Mapping

```python
COUNTRY_MAP = {
    "nigeria": "NG",
    "kenya": "KE",
    ...
}
```

---

## Example Mappings

| Query                  | Interpreted Filters                           |
| ---------------------- | --------------------------------------------- |
| young males            | gender=male + age 16–24                       |
| females above 30       | gender=female + age > 30                      |
| people from angola     | country_id=AO                                 |
| adult males from kenya | gender=male + age_group=adult + country_id=KE |

---

# 🔎 Advanced Filtering

## Supported Filters

| Filter                  | Type    |
| ----------------------- | ------- |
| gender                  | string  |
| age_group               | string  |
| country_id              | string  |
| min_age                 | integer |
| max_age                 | integer |
| min_gender_probability  | float   |
| min_country_probability | float   |

---

## Example

```http
GET /api/profiles?gender=male&country_id=NG&min_age=25
```

All filters are combinable.

---

# ↕️ Sorting

Supported fields:

* age
* created_at
* gender_probability

Example:

```http
GET /api/profiles?sort_by=age&order=desc
```

---

# 📄 Pagination

All paginated responses include:

```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "total_pages": 203,
  "links": {
    "self": "/api/profiles?page=1&limit=10",
    "next": "/api/profiles?page=2&limit=10",
    "prev": null
  },
  "data": []
}
```

---

# 📦 CLI Usage

The CLI is globally installable.

After installation:

```bash
insighta login
```

works from any directory.

---

# CLI Commands

## Authentication

```bash
insighta login
insighta logout
insighta whoami
```

---

## Profile Queries

```bash
insighta profiles list

insighta profiles list --gender male

insighta profiles list --country NG --age-group adult

insighta profiles list --min-age 25 --max-age 40

insighta profiles list --sort-by age --order desc

insighta profiles list --page 2 --limit 20
```

---

## Get Profile

```bash
insighta profiles get <id>
```

---

## Natural Language Search

```bash
insighta profiles search "young males from nigeria"
```

---

## Create Profile

```bash
insighta profiles create --name "Harriet Tubman"
```

---

## Export CSV

```bash
insighta profiles export --format csv

insighta profiles export --format csv --gender male --country NG
```

---

# 💾 CLI Credential Storage

Credentials are stored locally at:

```text
~/.insighta/credentials.json
```

Contains:

```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

---

# 🔄 CLI Auto Refresh Logic

The CLI automatically refreshes expired access tokens.

Flow:

```text
401 Unauthorized
        ↓
Attempt refresh token
        ↓
If refresh succeeds:
    retry request
Else:
    force re-login
```

---

# 📊 CLI UX Features

* Rich tables
* Loading spinners
* Structured error messages
* Automatic CSV saving
* Auth-aware requests

---

# 🚦 Rate Limiting

| Scope               | Limit                   |
| ------------------- | ----------------------- |
| `/auth/*`           | 10 requests/minute      |
| All other endpoints | 60 requests/minute/user |

Exceeded requests return:

```http
429 Too Many Requests
```

---

# 📝 Request Logging

Every request logs:

* HTTP method
* Endpoint
* Status code
* Response time

Example:

```text
GET /api/profiles 200 0.021s
```

---

# 🗄️ Database Schema

## Users

| Field         | Type      |
| ------------- | --------- |
| id            | UUID v7   |
| github_id     | VARCHAR   |
| username      | VARCHAR   |
| email         | VARCHAR   |
| avatar_url    | VARCHAR   |
| role          | ENUM      |
| is_active     | BOOLEAN   |
| last_login_at | TIMESTAMP |
| created_at    | TIMESTAMP |

---

## Profiles

| Field               | Type      |
| ------------------- | --------- |
| id                  | UUID v7   |
| name                | VARCHAR   |
| gender              | VARCHAR   |
| gender_probability  | FLOAT     |
| sample_size         | INTEGER   |
| age                 | INTEGER   |
| age_group           | VARCHAR   |
| country_id          | VARCHAR   |
| country_probability | FLOAT     |
| created_at          | TIMESTAMP |

---

## Refresh Tokens

| Field      | Type      |
| ---------- | --------- |
| id         | UUID v7   |
| user_id    | FK        |
| token      | TEXT      |
| is_revoked | BOOLEAN   |
| expires_at | TIMESTAMP |
| created_at | TIMESTAMP |

---

# ⚠️ Error Handling

All errors follow:

```json
{
  "status": "error",
  "message": "..."
}
```

---

## Common Status Codes

| Status | Meaning                   |
| ------ | ------------------------- |
| 400    | Invalid request           |
| 401    | Unauthorized              |
| 403    | Forbidden                 |
| 404    | Not found                 |
| 422    | Validation error          |
| 429    | Rate limit exceeded       |
| 500    | Internal server error     |
| 502    | Upstream provider failure |

---

# 🚀 Local Setup

## Clone Repository

```bash
git clone https://github.com/Sevenwings26/insighta-backend-system.git
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create `.env`

```env
DATABASE_URL=postgresql://user:password@host/db
JWT_SECRET=thisisasupersecret

GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=http://127.0.0.1:8000/auth/github/callback

SESSION_SECRET=thisasessionsecret
```

---

## Run Application

```bash
uvicorn api.main:app --reload
```

---

# 🧪 Testing

Swagger Docs:

```text
http://127.0.0.1:8000/docs
```

Recommended tools:

* Postman
* Swagger UI

---

# 📦 Key Dependencies

```txt
fastapi
uvicorn
sqlalchemy
psycopg2-binary
httpx
python-dotenv
uuid-utils
python-jose
authlib
itsdangerous
slowapi
rich
typer
```

---

# 📌 Notes

* UUID v7 improves index locality and pagination performance
* PKCE prevents OAuth interception attacks
* Refresh token rotation improves session security
* Natural language parsing is deterministic and rule-based
* API versioning enforced via `X-API-Version: 1` header

---

# License

MIT License
