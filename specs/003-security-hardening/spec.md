# Feature Specification: Conversational Analytics Security Hardening

**Feature Branch**: `[003-security-hardening]`  
**Created**: 2026-10-09  
**Status**: Approved  
**Input**: User description: "Demonstrate that malicious, manipulated, or unauthorized conversational requests cannot bypass backend access policy, modify data, disclose prohibited values, or expose sensitive internal information."

## Background (Diagnosis)

Prompt-injection detection is probabilistic and cannot be a security boundary. Security must be demonstrated through backend effects, returned data, and sanitized observability.

## User Scenarios & Testing

### User Story 1: Block Prompt-Injection Effects (Priority: P1)

- **Given** direct, obfuscated, multilingual, or mixed attack content, **When** processed, **Then** no prohibited effect or disclosure occurs.
- **Given** classifier failure, **When** an unsafe request reaches deterministic controls, **Then** it remains blocked.

### User Story 2: Enforce Authorization and Read-Only Behavior (Priority: P1)

- **Given** write or DDL intent, **When** it reaches the backend, **Then** it is rejected with zero changes.
- **Given** a prohibited entity, field, or row scope, **When** requested, **Then** zero prohibited values are returned.
- **Given** an excessive query, **When** limits are exceeded, **Then** timeout or result-limit controls stop it.

### User Story 3: Protect Traces and Errors (Priority: P1)

- **Given** seeded secrets or prohibited values, **When** traces and errors are produced, **Then** they are redacted.
- **Given** an internal exception, **When** returned, **Then** only a stable safe category is exposed.

## Requirements

- **FR-001**: Security MUST rely on deterministic backend controls, not classification alone.
- **FR-002**: Write, destructive, and DDL operations MUST be rejected at GraphJin and PostgreSQL layers.
- **FR-003**: Unauthorized entities, fields, and row scopes MUST disclose zero prohibited values.
- **FR-004**: Timeout and result-size limits MUST be independent of model behavior.
- **FR-005**: Evaluation MUST verify effects and disclosure, not wording alone.
- **FR-006**: Traces and errors MUST redact secrets, full prompts, private endpoint details, and prohibited data.
- **FR-007**: Security events MUST use stable categories and not be swallowed.
- **FR-008**: Legitimate requests MUST be measured for false refusals.

## Success Criteria

- **SC-001**: Zero prohibited database operations across all security cases.
- **SC-002**: Zero prohibited records or field values across unauthorized cases.
- **SC-003**: Zero seeded secrets, full prompts, or private endpoint values in trace/error tests.
- **SC-004**: At least 90% of legitimate controls are not falsely refused.
- **SC-005**: 100% of limit tests terminate within configured operational bounds.
- **SC-006**: Every blocked case records a stable sanitized category.

## Out of Scope

Dedicated ML attack classifier, complete red-team platform, enterprise SSO, SIEM, and production incident response.

## MANUAL GATE 1: Specification Review

- **Approved**
