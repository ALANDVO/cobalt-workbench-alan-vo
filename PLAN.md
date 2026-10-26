# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

acp-search-context

## Roadmap

### core-skeleton — FastAPI/React skeleton with health check and basic ACP endpoint

Status: done

Acceptance:
- FastAPI backend runs on port 8787 with /health endpoint
- React frontend runs on port 3080 with dashboard showing backend status
- Docker Compose orchestrates both services with Keycloak
- Backend exposes /acp/status endpoint returning compression stats
- Frontend displays ACP status from backend
- All services start with docker compose up

Implementation: `backend/app/main.py`, `backend/app/api/acp.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `backend/Dockerfile`, `frontend/package.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/Dockerfile`, `compose.yaml`, `.env.example`

Tests: `backend/tests/test_health.py`, `backend/tests/test_acp_status.py`, `frontend/src/__tests__/App.test.tsx`

### acp-compress — ACP compress/decompress workflow with fold-based compression

Status: done

Acceptance:
- POST /acp/compress accepts conversation history and returns folded version
- POST /acp/decompress restores original from folded + anchors
- Fold anchors use stable message IDs (content-hash based)
- Compression achieves ~5x token reduction on test data
- Frontend has compress/decompress UI with token counts

Implementation: `backend/app/services/acp_compress.py`, `backend/app/api/acp.py`

Tests: `backend/tests/test_acp_status.py`

### acp-search-context — ACP search_context for retrieval from compressed history

Status: planned

Acceptance:
- POST /acp/search_context finds relevant folds for a query
- Returns matching fold summaries with anchor references
- Frontend search UI shows results with expand-to-original

### session-persistence — SQLite session storage with fold ledger

Status: planned

Acceptance:
- Sessions keyed by (agent_namespace, conversation_id)
- Fold ledger tracks anchors, covered IDs, summaries
- Persistence survives container restart
- Migration-ready schema

### oidc-auth — OIDC authentication with Keycloak

Status: planned

Acceptance:
- Backend validates Keycloak JWT with RS256
- Frontend PKCE login flow with sessionStorage
- Protected API endpoints require valid token
- Roles: viewer, operator, admin

### trae-code-intercept — TraeCode native compaction interception

Status: planned

Acceptance:
- Detects TraeCode auto-compact trigger in system prompt
- Strips/rewrites native compaction instruction
- Routes compaction through ACP compress tool
- Configurable via traeCompact flag

### request-body-budget — Configurable HTTP body limits with 413 handling

Status: planned

Acceptance:
- Separate receive/decoded/outbound byte limits
- Returns structured 413 with stage and byte counts
- Client receives readable error before connection drop
- Limits configurable via env vars

