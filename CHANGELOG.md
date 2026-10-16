# Changelog

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
- Keycloak/OIDC settings for authentication