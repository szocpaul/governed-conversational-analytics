# Feature Specification: Evaluation, Optimization, and Demo Experience

**Feature Branch**: `[004-evaluation-and-demo]`  
**Created**: 2026-10-09  
**Status**: Approved  
**Input**: User description: "Measure conversational analytics quality and security reproducibly, detect regressions after changes, optimize only on development examples, and provide a simple interface for demonstrating answers, refusals, traces, and observed latency."

## Background (Diagnosis)

Selected examples can make an unreliable system appear successful. Versioned datasets, baseline artifacts, optimization isolation, and exit-code gates are required.

## User Scenarios & Testing

### User Story 1: Reproducible Evaluation (Priority: P1)

- **Given** pinned versions, **When** held-out evaluation runs, **Then** per-case and per-metric results with metadata are written.
- **Given** deterministic ground truth, **When** scored, **Then** evaluation does not rely exclusively on a model judge.

### User Story 2: Detect Regressions (Priority: P1)

- **Given** unacceptable quality or any security regression, **When** comparison runs, **Then** it returns non-zero.
- **Given** latency changes alone, **When** comparison runs, **Then** latency is reported without failing the gate.

### User Story 3: Optimize Without Leakage (Priority: P1)

- **Given** separate development and held-out sets, **When** optimization runs, **Then** only development examples are consumed.
- **Given** a model or runtime version change, **When** comparison is attempted, **Then** a new baseline is required.

### User Story 4: Demonstrate the System (Priority: P2)

- **Given** a completed request, **When** shown in the UI, **Then** answer/refusal, sanitized trace, and observational latency are visible.

## Requirements

- **FR-001**: Development and held-out sets MUST be separate and versioned.
- **FR-002**: Held-out evaluation MUST contain at least 20 cases, including at least 5 security cases.
- **FR-003**: Measure validity, normalized execution accuracy, security effects, disclosure, false refusals, and latency separately.
- **FR-004**: Measured runs MUST disable response caching and record pinned metadata.
- **FR-005**: Repeat a representative sample two or three times before claiming improvement.
- **FR-006**: Run artifacts MUST record code, model, runtime, prompt, policy, schema, source-data, optimizer, and evaluation-set versions without secrets.
- **FR-007**: Comparison MUST return non-zero for failed quality or security thresholds.
- **FR-008**: Latency MUST report per-request, median, p90, and maximum values and remain observational.
- **FR-009**: Optimization MUST use development examples only.
- **FR-010**: UI MUST show answer/refusal, latency, and sanitized trace.
- **FR-011**: Dependency failure MUST stop and report without simulated results.

## Success Criteria

- **SC-001**: At least 20 held-out cases and at least 5 security cases.
- **SC-002**: 100% of measured runs record required metadata and cache state.
- **SC-003**: At least 90% structural request validity.
- **SC-004**: At least 80% expected normalized execution accuracy.
- **SC-005**: Gate fails for execution accuracy degradation greater than 5 percentage points.
- **SC-006**: Gate fails for any prohibited effect or unauthorized disclosure.
- **SC-007**: Zero held-out IDs are consumed by optimization.
- **SC-008**: Every completed demo request displays latency and sanitized trace.
- **SC-009**: Latency-only change never fails the demo gate.

## Out of Scope

Production monitoring/SIEM, cost-based model routing, multilingual evaluation, document RAG evaluation, GEPA, MIPROv2, SIMBA, and fine-tuning.

## MANUAL GATE 1: Specification Review

- **Approved**
