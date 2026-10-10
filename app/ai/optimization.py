"""BootstrapFewShot optimization isolated to development cases (spec 004, T005/T006).

The ONLY approved optimizer is dspy.BootstrapFewShot with a bounded
configuration. Optimization consumes ONLY development case IDs; held-out IDs
are guarded against leakage (FR-009, SC-007). The binary metric returns 1.0
only when every mandatory check passes; otherwise 0.0 (no partial credit).

GEPA, MIPROv2, SIMBA, and fine-tuning are prohibited here.
"""
from __future__ import annotations

import hashlib
import json
import os

import dspy

from evaluation import metrics
from evaluation.schemas import load_dev_cases, load_held_out_cases

_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OPTIMIZED_PROGRAM_PATH = os.path.join(
    _REPO, "app", "ai", "optimized_program.json")
OPTIMIZATION_RUN_PATH = os.path.join(
    _REPO, "artifacts", "optimization-run.json")

MIN_DEV_EXAMPLES = 12


# ---------------------------------------------------------------------------
# Optimizer configuration (bounded, approved)
# ---------------------------------------------------------------------------

def optimizer_config() -> dict:
    """Return the approved bounded BootstrapFewShot configuration."""
    return {
        "metric_threshold": 1.0,
        "max_bootstrapped_demos": 4,
        "max_labeled_demos": 4,
        "max_rounds": 1,
        "max_errors": 3,
    }


# ---------------------------------------------------------------------------
# Isolation guards (SC-007)
# ---------------------------------------------------------------------------

def assert_no_held_out_leakage(case_ids) -> None:
    """Raise AssertionError if any held-out ID is present."""
    held_ids = set(load_held_out_cases().ids)
    leaked = [cid for cid in case_ids if cid in held_ids]
    if leaked:
        raise AssertionError(
            f"held-out case IDs leaked into optimization: {leaked}")


def build_trainset(extra_cases=None) -> list[dspy.Example]:
    """Build the optimization trainset from development cases ONLY.

    Each example carries the labeled governed request and normalized expected
    result. Any non-development (held-out) case raises ValueError (SC-007).
    """
    dev = load_dev_cases()
    held_ids = set(load_held_out_cases().ids)

    cases = list(dev.cases)
    if extra_cases:
        for c in extra_cases:
            if c.id in held_ids:
                raise ValueError(
                    f"held-out case {c.id!r} must not enter optimization")
            cases.append(c)

    trainset = []
    for c in cases:
        if c.id in held_ids:
            raise ValueError(
                f"held-out case {c.id!r} must not enter optimization")
        expected = c.expected or {}
        # Only supported analytics cases with a labeled request are usable
        # for bootstrap demonstrations.
        if "request" not in expected or "result" not in expected:
            continue
        ex = dspy.Example(
            case_id=c.id,
            question=c.question,
            expected_request=expected["request"],
            expected_result=expected["result"],
        ).with_inputs("question")
        trainset.append(ex)

    assert_no_held_out_leakage([e.case_id for e in trainset])
    return trainset


# ---------------------------------------------------------------------------
# Binary optimizer metric
# ---------------------------------------------------------------------------

def _execute_read_only(request: dict):
    """Execute a validated read-only request via GraphJin; return the
    normalized result dict, or None on any failure. Never issues writes."""
    try:
        from app.api.schemas import StructuredQueryRequest
        from app.data.graphjin_client import GraphJinClient, GraphJinError
        from app.data.result_normalizer import normalize_result

        req = StructuredQueryRequest.model_validate(request)
        url = os.environ.get(
            "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")
        client = GraphJinClient(url, timeout=30.0)
        raw = client.execute(req)
        evidence = normalize_result(req, raw)
        # Apply the deterministic having post-filter so the compared result
        # matches the pipeline's governed output (spec 005, research D4).
        from app.data.result_normalizer import apply_having
        evidence = apply_having(evidence, req)
        if evidence.aggregate:
            return dict(evidence.aggregate)
        if req.group_by:
            return {"groups": [dict(r) for r in evidence.rows],
                    "row_count": evidence.row_count}
        return {"row_count": evidence.row_count}
    except Exception:  # noqa: BLE001
        return None


def text_to_query_metric(example, pred, trace=None) -> float:
    """Return 1.0 only when every mandatory check passes; else 0.0.

    Mandatory checks:
      - structured output validates against the governed schema;
      - the request is read-only and policy-allowed;
      - governed execution succeeded (pred.executed with a result);
      - the normalized execution result matches the labeled expected result;
      - no prohibited effect or unauthorized disclosure occurred.
    """
    request = getattr(pred, "request", None)
    executed = getattr(pred, "executed", None)
    execution_result = getattr(pred, "execution_result", None)
    prohibited = getattr(pred, "prohibited_effect", False)
    disclosed = getattr(pred, "disclosure", False)

    # Security: any prohibited effect or disclosure fails immediately.
    if prohibited or disclosed:
        return 0.0

    # Structured output must exist and validate.
    if request is None:
        return 0.0
    if metrics.structural_validity(request) != 1.0:
        return 0.0

    # Request must be read-only and policy-allowed.
    if not metrics.is_read_only(request):
        return 0.0

    # Governed execution must succeed. When the program explicitly reports a
    # failed execution, fail. When the program did not attempt execution
    # itself (plain QueryProgram leaves executed=None), the metric executes
    # the validated read-only request via the governed GraphJin client to
    # verify successful execution and obtain the normalized result.
    if executed is False:
        return 0.0
    if execution_result is None:
        execution_result = _execute_read_only(request)
        if execution_result is None:
            return 0.0

    # Normalized result must match the labeled expected result. When the
    # label does not include group rows, compare on the labeled keys only
    # (a grouped request labeled by row_count is still a valid demo).
    expected_result = example.expected_result
    if isinstance(execution_result, dict) and \
            isinstance(expected_result, dict) and \
            "groups" in execution_result and "groups" not in expected_result:
        execution_result = {k: v for k, v in execution_result.items()
                            if k in expected_result}
    if metrics.execution_accuracy(execution_result,
                                  expected_result) != 1.0:
        return 0.0

    return 1.0


# ---------------------------------------------------------------------------
# Compilation (T006)
# ---------------------------------------------------------------------------

def compile_program(program=None, trainset=None):
    """Compile the query program with BootstrapFewShot on development cases.

    Returns (optimized_program, run_metadata). Raises RuntimeError when fewer
    than MIN_DEV_EXAMPLES valid labeled development examples exist (the caller
    must then record the unoptimized baseline and skip optimization).
    """
    if trainset is None:
        trainset = build_trainset()
    if len(trainset) < MIN_DEV_EXAMPLES:
        raise RuntimeError(
            f"only {len(trainset)} valid labeled development examples; "
            f"need >= {MIN_DEV_EXAMPLES}. Record the unoptimized baseline "
            f"and skip optimization (no held-out substitution).")

    if program is None:
        from app.ai.query_program import QueryProgram
        program = QueryProgram()

    cfg = optimizer_config()
    optimizer = dspy.BootstrapFewShot(
        metric=text_to_query_metric,
        metric_threshold=cfg["metric_threshold"],
        max_bootstrapped_demos=cfg["max_bootstrapped_demos"],
        max_labeled_demos=cfg["max_labeled_demos"],
        max_rounds=cfg["max_rounds"],
        max_errors=cfg["max_errors"],
    )
    optimized = optimizer.compile(program, trainset=trainset)

    consumed_ids = [e.case_id for e in trainset]
    assert_no_held_out_leakage(consumed_ids)

    return optimized, {
        "optimizer": "dspy.BootstrapFewShot",
        "config": cfg,
        "input_case_ids": consumed_ids,
        "trainset_size": len(trainset),
    }


# ---------------------------------------------------------------------------
# Executable program used during bootstrapping (T006)
# ---------------------------------------------------------------------------


class ExecutableQueryProgram(dspy.Module):
    """Wrap QueryProgram and execute the planned request via GraphJin.

    BootstrapFewShot's teacher must produce a prediction carrying the governed
    request, whether it executed, and the normalized execution result so the
    binary metric can verify every mandatory check. This module never issues
    writes: execution goes through the governed GraphJin client only.
    """

    def __init__(self):
        super().__init__()
        from app.ai.query_program import QueryProgram
        self.plan = QueryProgram()

    def forward(self, question: str) -> dspy.Prediction:
        from app.data.graphjin_client import GraphJinClient, GraphJinError
        from app.data.result_normalizer import normalize_result

        planned = self.plan(question=question)
        request = planned.request
        executed = False
        execution_result = None
        prohibited = False
        disclosed = False

        if request is not None:
            try:
                url = os.environ.get(
                    "GRAPHJIN_GRAPHQL_URL",
                    "http://127.0.0.1:8081/api/v1/graphql")
                client = GraphJinClient(url, timeout=30.0)
                raw = client.execute(request)
                from app.data.result_normalizer import apply_having
                evidence = apply_having(normalize_result(request, raw),
                                        request)
                executed = True
                if evidence.aggregate:
                    execution_result = dict(evidence.aggregate)
                elif getattr(request, "group_by", None):
                    execution_result = {
                        "groups": [dict(r) for r in evidence.rows],
                        "row_count": evidence.row_count}
                else:
                    execution_result = {"row_count": evidence.row_count}
            except GraphJinError:
                executed = False
                execution_result = None

        return dspy.Prediction(
            classification=planned.classification,
            rationale=planned.rationale,
            request=(
                request.model_dump() if hasattr(request, "model_dump")
                else request),
            executed=executed,
            execution_result=execution_result,
            prohibited_effect=prohibited,
            disclosure=disclosed,
        )


# ---------------------------------------------------------------------------
# Runner (T006)
# ---------------------------------------------------------------------------

def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_optimization(output_program: str = OPTIMIZED_PROGRAM_PATH,
                     run_artifact: str = OPTIMIZATION_RUN_PATH) -> int:
    """Compile BootstrapFewShot on development cases and save artifacts.

    Returns 0 on success, 2 when optimization is skipped (too few dev
    examples), 1 on error. Never uses held-out cases (SC-007).
    """
    from dotenv import load_dotenv
    load_dotenv()
    os.environ["LLM_TEMPERATURE"] = "0"
    os.environ["LLM_CACHE"] = "false"

    from app.ai.llm import LLMConfig, configure_dspy
    configure_dspy(LLMConfig.from_env())

    trainset = build_trainset()
    input_ids = [e.case_id for e in trainset]
    assert_no_held_out_leakage(input_ids)

    run_meta = {
        "optimizer": "dspy.BootstrapFewShot",
        "config": optimizer_config(),
        "input_case_ids": input_ids,
        "trainset_size": len(trainset),
        "held_out_ids_consumed": 0,
        "errors": [],
        "accepted_demo_ids": [],
        "output_program_sha256": None,
        "versions": {},
    }

    if len(trainset) < MIN_DEV_EXAMPLES:
        run_meta["errors"].append(
            f"skipped: only {len(trainset)} valid labeled development "
            f"examples (< {MIN_DEV_EXAMPLES})")
        os.makedirs(os.path.dirname(run_artifact), exist_ok=True)
        with open(run_artifact, "w") as f:
            json.dump(run_meta, f, indent=2)
        print(json.dumps({"skipped": True, "trainset_size": len(trainset)}))
        return 2

    try:
        optimized, meta = compile_program(trainset=trainset)
        os.makedirs(os.path.dirname(output_program), exist_ok=True)
        optimized.save(output_program)

        # Record accepted demonstration IDs. DSPy strips non-input/output
        # fields when attaching demos, so map each demo's question text back
        # to its development case ID.
        q_to_id = {e.question: e.case_id for e in trainset}
        accepted = []
        try:
            for predictor in optimized.predictors():
                for demo in getattr(predictor, "demos", []) or []:
                    q = getattr(demo, "question", None)
                    cid = q_to_id.get(q)
                    if cid:
                        accepted.append(cid)
        except Exception:  # noqa: BLE001
            pass
        run_meta["accepted_demo_ids"] = sorted(set(accepted))
        # Isolation proof: accepted demos must be a subset of dev IDs.
        assert_no_held_out_leakage(run_meta["accepted_demo_ids"])
        run_meta["output_program_sha256"] = _sha256(output_program)
        run_meta["versions"] = {
            "dspy": dspy.__version__,
            "model_id": os.environ.get("LLM_MODEL", ""),
            "temperature": 0.0,
            "cache": False,
        }
    except Exception as exc:  # noqa: BLE001
        run_meta["errors"].append(f"optimization failed: {exc}")
        os.makedirs(os.path.dirname(run_artifact), exist_ok=True)
        with open(run_artifact, "w") as f:
            json.dump(run_meta, f, indent=2)
        print(json.dumps({"error": str(exc)}))
        return 1

    os.makedirs(os.path.dirname(run_artifact), exist_ok=True)
    with open(run_artifact, "w") as f:
        json.dump(run_meta, f, indent=2)
    print(json.dumps({"compiled": True,
                      "trainset_size": len(trainset),
                      "accepted_demos": run_meta["accepted_demo_ids"],
                      "program_sha256": run_meta["output_program_sha256"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_optimization())
