# Changelog

## 1.3.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

### Added (acp-search-context)
- `search_folds()` service function: Jaccard similarity + substring + role relevance scoring for fold anchors
- `SearchContextRequest`, `SearchContextResult`, `SearchContextResponse` Pydantic models
- `search_context()` service function orchestrating search over fold anchors
- POST `/acp/search_context` endpoint returning ranked fold matches with scores
- Frontend search UI: query input, results table with anchor ID, summary, score, token counts, index range
- Backend test coverage: search_context endpoint, empty query, no anchors edge cases

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-16

### Added
- FastAPI backend with `/health`, `/health/ready`, and `/acp/status` endpoints
- React + TypeScript + Vite frontend with dashboard showing ACP status
- Docker Compose configuration for backend, frontend, and Keycloak
- Keycloak realm configuration with viewer/operator/admin roles
- Pydantic-based configuration management with environment variables
- Comprehensive test suite: 5 backend tests (pytest), 4 frontend tests (vitest)
- Type checking: mypy for backend, tsc for frontend
- Non-root Dockerfiles for both services
- CORS configuration for local development
- Request timing middleware and global exception handler
- ACP status mock data showing sessions, folds, and token savings

### Configuration
- Configurable ACP parameters: window tokens, compression ratio, fold threshold
- Configurable HTTP body limits: receive, decoded, outbound
- LLM provider settings (opt-in, advisory only)

## [1.0.1] - 2026-10-26

### Added
- ACP fold-based compression service (`backend/app/services/acp_compress.py`)
- Content-hash based stable message IDs for fold anchors
- `fold_conversation()` — groups messages into summarized folds with target compression ratio
- `unfold_conversation()` — expands fold anchors into structured summaries
- Token estimation (~4 chars/token) and message summarization utilities
- `/acp/compress` endpoint: accepts messages, preserve_recent, returns folded messages + anchors + token counts
- `/acp/decompress` endpoint: expands fold anchors from folded messages + anchor metadata
- Real compression ratio calculation based on actual token estimates
- Test coverage in existing `test_acp_status.py` for compress/decompress endpoints
- Keycloak/OIDC settings for authentication

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
