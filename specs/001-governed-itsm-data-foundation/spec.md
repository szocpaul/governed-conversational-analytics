# Feature Specification: Governed ITSM Data Foundation

**Feature Branch**: `[001-governed-itsm-data-foundation]`  
**Created**: 2026-10-09  
**Status**: Approved  
**Input**: User description: "Provide a reproducible, relational ITSM demonstration dataset through a read-only, policy-controlled query surface so later application features can access it safely and consistently."

## Background (Diagnosis)

Conversational analytics cannot be evaluated reliably when source data is mutable, manually assembled, or accessed with unrestricted credentials. A stable, reproducible, governed data foundation is required first.

## User Scenarios & Testing

### User Story 1: Reproducible ITSM Data Import (Priority: P1)

As a developer, I want to reproduce the same relational ITSM dataset from a pinned public source.

**Independent Test**: Starting from an empty environment, create the database, import the pinned source, and verify provenance, row counts, required fields, and relationships.

**Acceptance Scenarios**:
- **Given** a verified source revision, **When** import runs, **Then** all expected entities load with provenance and checksums.
- **Given** invalid required fields or relationships, **When** validation runs, **Then** import fails atomically.
- **Given** the same source revision, **When** reset and import repeat, **Then** validated results are identical.

### User Story 2: Read-Only Governed Query Access (Priority: P1)

As a system owner, I want access restricted to approved entities, fields, relationships, and read operations.

**Independent Test**: Execute allowed reads and prohibited write, DDL, entity, and field requests.

**Acceptance Scenarios**:
- **Given** an allowed analytical query, **When** submitted, **Then** expected records are returned.
- **Given** a modifying or DDL operation, **When** submitted, **Then** it is rejected with zero changes.
- **Given** a prohibited entity or field, **When** requested, **Then** no prohibited value is returned.

## Edge Cases

- Source revision or license is unavailable.
- Raw files change under the same names.
- Optional fields are empty.
- Foreign-key targets are missing.
- Repeated import could duplicate data.
- PostgreSQL or GraphJin is unavailable.

## Requirements

- **FR-001**: The system MUST use a pinned public synthetic ITSM dataset with source, revision, license, attribution, and checksums.
- **FR-002**: Raw source files MUST remain unchanged.
- **FR-003**: PostgreSQL service, application database, schema, tables, indexes, owner role, and read-only role MUST be reproducibly created.
- **FR-004**: Initialization and import MUST be idempotent and atomic.
- **FR-005**: Import MUST validate row counts, required fields, business keys, and foreign keys.
- **FR-006**: Access MUST be read-only at GraphJin and PostgreSQL layers.
- **FR-007**: Allowed entities, fields, relationships, operations, limits, and timeouts MUST be explicit.
- **FR-008**: Failures MUST be visible and MUST NOT cause silent substitution or generated replacement records.

### Key Entities

Source Dataset Revision, Merchant, Support Agent, Ticket, Access Policy, Import Manifest.

## Success Criteria

- **SC-001**: 100% of raw files have recorded SHA-256 checksums and revision metadata.
- **SC-002**: 100% of required fields pass validation before import acceptance.
- **SC-003**: 100% of non-null foreign keys resolve.
- **SC-004**: Reimport produces zero duplicate business keys.
- **SC-005**: 100% of tested write and DDL operations are rejected with zero changes.
- **SC-006**: 100% of unauthorized entity and field tests disclose zero prohibited values.

## Out of Scope

Natural-language interpretation, prompt-injection classification, model optimization, and UI. These restart after the foundation passes its gates.

## MANUAL GATE 1: Specification Review

- **Approved**
