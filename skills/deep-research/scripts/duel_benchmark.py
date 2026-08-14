#!/usr/bin/env python3
"""Private, reproducible Researcher vs Parallel five-question benchmark.

The controller never drives Researcher itself. It freezes completed investigate
runs, gates one paid Parallel attempt behind --confirm-paid, creates blind A/B
material, and refuses to report incomplete judgment. Stdlib only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_SUITE = REPO_ROOT / "benchmarks" / "duel-v1.json"
DEFAULT_RUNTIME_ROOT = REPO_ROOT / "research"
EXPECTED_QUESTION_IDS = ["q01", "q02", "q03", "q04", "q05"]
RUBRIC_DIMENSIONS = (
    "usefulness",
    "correctness",
    "evidence_fit",
    "freshness",
    "uncertainty_honesty",
)


def _load_eval_harness():
    path = SCRIPT_DIR / "eval_harness.py"
    spec = importlib.util.spec_from_file_location("duel_eval_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eval_harness = _load_eval_harness()


class BenchmarkError(ValueError):
    """A user-correctable bundle, consent, or judgment violation."""


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise BenchmarkError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest_json(value):
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_private_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def _known_secrets():
    values = []
    for name, value in os.environ.items():
        upper = name.upper()
        if value and any(token in upper for token in ("API_KEY", "ACCESS_TOKEN", "BOT_TOKEN")):
            values.append(value.strip())
    secrets_dir = eval_harness._default_secrets_dir()
    if secrets_dir.is_dir():
        for path in secrets_dir.iterdir():
            if not path.is_file() or not any(
                marker in path.name.lower() for marker in ("key", "token")
            ):
                continue
            try:
                raw = path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if raw:
                values.append(raw)
    return tuple(value for value in values if value)


def _sanitize(value):
    return eval_harness._sanitize_artifact(value, _known_secrets())


def _assert_relative_path(value, label="path"):
    pure = PurePosixPath(str(value))
    if pure.is_absolute() or ".." in pure.parts:
        raise BenchmarkError(f"{label} must be a safe relative path: {value!r}")
    return pure.as_posix()


def write_private_text(path, value):
    eval_harness._atomic_write_private(Path(path), str(_sanitize(value)))


def write_private_json(path, value):
    safe = _sanitize(value)
    eval_harness._atomic_write_private(
        Path(path),
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchmarkError(f"missing {label}: {Path(path).name}") from exc
    except (OSError, ValueError) as exc:
        raise BenchmarkError(f"invalid {label}: {Path(path).name}") from exc
    if not isinstance(value, dict):
        raise BenchmarkError(f"{label} must be a JSON object")
    return value


def load_suite(path=DEFAULT_SUITE):
    suite = _read_json(path, "benchmark suite")
    questions = suite.get("questions")
    if not isinstance(questions, list) or len(questions) != 5:
        raise BenchmarkError("benchmark suite must contain exactly five questions")
    if [question.get("id") for question in questions] != EXPECTED_QUESTION_IDS:
        raise BenchmarkError("benchmark question IDs must be q01 through q05 in order")
    if any(not isinstance(question.get("text"), str) or not question["text"].strip()
           for question in questions):
        raise BenchmarkError("every benchmark question must contain non-empty text")
    if suite.get("language") != "en":
        raise BenchmarkError("benchmark language must remain English")
    dimensions = tuple((suite.get("rubric") or {}).get("dimensions") or ())
    if dimensions != RUBRIC_DIMENSIONS:
        raise BenchmarkError("benchmark rubric dimensions have changed")
    if (suite.get("parallel") or {}).get("processor") != "ultra":
        raise BenchmarkError("official benchmark processor must remain ultra")
    rules = suite.get("rules") or {}
    if rules.get("per_question_win_margin") != 3 or rules.get("overall_wins_required") != 3:
        raise BenchmarkError("benchmark winner thresholds have changed")
    return suite


def _question(suite, question_id):
    for question in suite["questions"]:
        if question["id"] == question_id:
            return question
    raise BenchmarkError(f"unknown question ID: {question_id}")


def _git_sha(repo_root):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BenchmarkError("cannot determine repository git SHA") from exc
    return result.stdout.strip()


def _package_version(repo_root):
    try:
        plugin = json.loads(
            (Path(repo_root) / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return "unknown"
    return str(plugin.get("version") or "unknown")


def _configured_provider_probe():
    path = SCRIPT_DIR / "detect_state.py"
    spec = importlib.util.spec_from_file_location("duel_detect_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = module.collect_state()
    direct = state.get("providers") or {}
    openrouter = bool(direct.get("openrouter"))

    def lens(name):
        if direct.get(name):
            return True, "direct"
        if openrouter:
            return True, "openrouter_fallback"
        return False, "unavailable"

    gemini, gemini_route = lens("gemini")
    grok, grok_route = lens("grok")
    perplexity, perplexity_route = lens("perplexity")
    parallel = bool(eval_harness._read_parallel_key())
    telegram = bool(state.get("telegram_session"))
    scrapecreators = bool(direct.get("scrapecreators"))
    providers = {
        "parallel": parallel,
        "gemini": gemini,
        "grok": grok,
        "openrouter": openrouter,
        "perplexity": perplexity,
        "telegram": telegram,
        "scrapecreators": scrapecreators,
    }
    routes = {
        "parallel": "direct" if parallel else "unavailable",
        "gemini": gemini_route,
        "grok": grok_route,
        "openrouter": "direct" if openrouter else "unavailable",
        "perplexity": perplexity_route,
        "telegram": "client_session" if telegram else "unavailable",
        "scrapecreators": "direct_pay_per_use" if scrapecreators else "unavailable",
    }
    return providers, routes


def _default_bundle_path(now):
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_RUNTIME_ROOT / f"duel-v1-{stamp}"


def init_bundle(suite_path=DEFAULT_SUITE, bundle_dir=None, *, repo_root=REPO_ROOT,
                now=None, git_sha=None, provider_probe=None,
                price_checked=False):
    now_fn = now or _utc_now
    started = now_fn()
    bundle_dir = Path(bundle_dir) if bundle_dir is not None else _default_bundle_path(started)
    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise BenchmarkError(f"bundle directory is not empty: {bundle_dir.name}")
    suite = load_suite(suite_path)
    if _digest_json(suite) != _digest_json(load_suite(DEFAULT_SUITE)):
        raise BenchmarkError("init accepts only the committed duel-v1 suite")
    digest = _digest_json(suite)
    sha_fn = git_sha or _git_sha
    probe_fn = provider_probe or _configured_provider_probe
    probe_result = probe_fn()
    if isinstance(probe_result, tuple) and len(probe_result) == 2:
        providers, provider_routes = probe_result
    else:
        providers = probe_result
        provider_routes = {
            name: "configured" if available else "unavailable"
            for name, available in (providers or {}).items()
        }
    if not isinstance(providers, dict) or any(not isinstance(v, bool) for v in providers.values()):
        raise BenchmarkError("provider preflight must contain booleans only")
    if not isinstance(provider_routes, dict) or set(provider_routes) != set(providers):
        raise BenchmarkError("provider route preflight must match provider availability")
    _ensure_private_dir(bundle_dir)

    created_at = _iso(started)
    deadline_at = _iso(started + timedelta(
        hours=suite["rules"]["all_official_attempts_within_hours"]
    ))
    metadata = {
        "schema_version": 1,
        "bundle_id": bundle_dir.name,
        "suite_id": suite["suite_id"],
        "suite_digest": digest,
        "state": "initialized",
        "created_at": created_at,
        "deadline_at": deadline_at,
        "git_sha": sha_fn(Path(repo_root)),
        "versions": {
            "python": sys.version.split()[0],
            "zbs_researcher": _package_version(repo_root),
            "duel_schema": 1,
        },
        "question_paths": [f"questions/{question['id']}/question.json"
                           for question in suite["questions"]],
    }
    frozen = {"digest": digest, "suite": suite}
    price = suite["parallel"]["published_price"]
    preflight = {
        "schema_version": 1,
        "captured_at": created_at,
        "providers": providers,
        "provider_routes": provider_routes,
        "budgets": suite["budgets"],
        "parallel": {
            "processor": suite["parallel"]["processor"],
            "amount_per_successful_run": price["amount_per_successful_run"],
            "five_run_total": price["five_run_total"],
            "verified_on": price["verified_on"],
            "basis": price["basis"],
            "pricing_source": price["pricing_source"],
            "processor_source": price["processor_source"],
        },
        "paid_authorized": False,
        "pricing_checked_for_live_run": bool(price_checked),
        "pricing_checked_at": created_at if price_checked else None,
        "note": "Initialization records readiness only and authorizes no paid call.",
    }
    write_private_json(bundle_dir / "suite.json", frozen)
    write_private_json(bundle_dir / "preflight.json", preflight)
    for question in suite["questions"]:
        qdir = _ensure_private_dir(bundle_dir / "questions" / question["id"])
        write_private_json(qdir / "question.json", question)
    write_private_json(bundle_dir / "bundle.json", metadata)
    return metadata


def load_bundle(bundle_dir):
    bundle_dir = Path(bundle_dir)
    metadata = _read_json(bundle_dir / "bundle.json", "bundle metadata")
    frozen = _read_json(bundle_dir / "suite.json", "frozen suite")
    suite = frozen.get("suite")
    if not isinstance(suite, dict):
        raise BenchmarkError("frozen suite is missing its suite object")
    expected = frozen.get("digest")
    actual = _digest_json(suite)
    if expected != actual or metadata.get("suite_digest") != actual:
        raise BenchmarkError("bundle suite digest mismatch; frozen inputs were modified")
    committed_digest = _digest_json(load_suite(DEFAULT_SUITE))
    if actual != committed_digest:
        raise BenchmarkError(
            "bundle no longer matches the committed duel-v1 suite; "
            "runtime questions cannot be rewritten"
        )
    load_suite_object = suite
    # Apply the same validation as a committed suite without writing a temp file.
    if [q.get("id") for q in load_suite_object.get("questions", [])] != EXPECTED_QUESTION_IDS:
        raise BenchmarkError("bundle suite question set is invalid")
    if tuple((suite.get("rubric") or {}).get("dimensions") or ()) != RUBRIC_DIMENSIONS:
        raise BenchmarkError("bundle suite rubric is invalid")
    return {"metadata": metadata, "suite": suite}


def _set_bundle_state(bundle_dir, state):
    path = Path(bundle_dir) / "bundle.json"
    metadata = _read_json(path, "bundle metadata")
    metadata["state"] = state
    write_private_json(path, metadata)


def _bundle_relative(bundle_dir, path):
    try:
        relative = Path(path).resolve().relative_to(Path(bundle_dir).resolve())
    except ValueError as exc:
        raise BenchmarkError("artifact escaped the benchmark bundle") from exc
    return _assert_relative_path(relative.as_posix())


def _copy_private_tree(source, target):
    source = Path(source)
    target = Path(target)
    copied = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise BenchmarkError(f"Researcher run contains a symlink: {path.name}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        _ensure_private_dir(destination.parent)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise BenchmarkError(f"Researcher artifact is not UTF-8 text: {relative}") from exc
        write_private_text(destination, content)
        copied.append(destination)
    return copied


def _duration_from_manifest(manifest):
    if not manifest.get("started") or not manifest.get("finished"):
        return None
    try:
        return max(
            (_parse_time(manifest["finished"]) - _parse_time(manifest["started"]))
            .total_seconds(),
            0.0,
        )
    except BenchmarkError:
        return None


def snapshot_researcher(bundle_dir, question_id, run_dir, *, now=None,
                        technical_failure_reason=None):
    context = load_bundle(bundle_dir)
    suite = context["suite"]
    question = _question(suite, question_id)
    bundle_dir = Path(bundle_dir)
    run_dir = Path(run_dir)
    timestamp = (now or _utc_now)()
    created_at = _parse_time(context["metadata"]["created_at"])
    deadline_at = _parse_time(context["metadata"]["deadline_at"])
    if timestamp < created_at or timestamp > deadline_at:
        raise BenchmarkError("Researcher snapshot is outside the frozen 24-hour window")
    destination = bundle_dir / "questions" / question_id / "researcher"
    receipt_path = destination / "snapshot.json"
    if receipt_path.exists():
        raise BenchmarkError(f"Researcher snapshot for {question_id} is already frozen")
    required = {
        "topic": run_dir / "_topic.txt",
        "plan": run_dir / "research-plan.md",
        "manifest": run_dir / "manifest.json",
        "synthesis": run_dir / "synthesis.md",
    }
    common_required = ("topic", "plan") if technical_failure_reason else tuple(required)
    for label in common_required:
        path = required[label]
        if not path.is_file() or not path.stat().st_size:
            raise BenchmarkError(f"Researcher run is missing non-empty {label}: {path.name}")
    topic = required["topic"].read_text(encoding="utf-8").strip()
    if topic != question["text"]:
        raise BenchmarkError("Researcher topic does not match the exact frozen question")
    plan = required["plan"].read_text(encoding="utf-8")
    if question["text"] not in plan or "source plan" not in plan.lower():
        raise BenchmarkError("research-plan.md must contain the exact question and a source plan")

    if technical_failure_reason:
        reason = str(technical_failure_reason).strip()
        if not reason:
            raise BenchmarkError("technical Researcher failure requires a non-empty reason")
        manifest = (
            _read_json(required["manifest"], "Researcher manifest")
            if required["manifest"].is_file() else {}
        )
        channels = manifest.get("channels") or {}
        has_success = any(
            isinstance(value, dict) and value.get("status") == "ok"
            for value in channels.values()
        )
        if required["synthesis"].is_file() and required["synthesis"].stat().st_size and has_success:
            raise BenchmarkError(
                "a completed Researcher answer is not a technical failure; a poor answer cannot be retried"
            )
        failures_root = destination / "technical-failures"
        existing = sorted(failures_root.glob("failure-*/failure.json"))
        number = len(existing) + 1
        attempt_dir = _ensure_private_dir(failures_root / f"failure-{number:03d}")
        copied = _copy_private_tree(run_dir, attempt_dir / "run")
        failure = {
            "schema_version": 1,
            "question_id": question_id,
            "attempt_number": number,
            "state": "technical_failure",
            "reason": reason,
            "captured_at": _iso(timestamp),
            "attempt_path": _bundle_relative(bundle_dir, attempt_dir),
            "files": [_bundle_relative(bundle_dir, path) for path in copied],
        }
        write_private_json(attempt_dir / "failure.json", failure)
        _set_bundle_state(bundle_dir, "collecting")
        return failure

    manifest = _read_json(required["manifest"], "Researcher manifest")
    if manifest.get("mode") not in (None, "investigate"):
        raise BenchmarkError("Researcher snapshot must come from investigate mode")
    drill_rounds = manifest.get("drill_rounds")
    if isinstance(drill_rounds, int) and drill_rounds > suite["researcher"]["max_drill_rounds"]:
        raise BenchmarkError("Researcher run exceeds the four-drill-round limit")
    for field in ("started", "finished"):
        if manifest.get(field):
            event_time = _parse_time(manifest[field])
            if event_time < created_at or event_time > deadline_at:
                raise BenchmarkError(
                    f"Researcher manifest {field} is outside the frozen 24-hour window"
                )
    channels = manifest.get("channels") or {}
    if not any(isinstance(value, dict) and value.get("status") == "ok"
               for value in channels.values()):
        raise BenchmarkError("Researcher manifest has no successful source")
    raw_files = [
        path for path in run_dir.rglob("*.md")
        if path.name not in {"research-plan.md", "synthesis.md"}
        and not path.name.endswith(".ERROR.md")
    ]
    if not raw_files:
        raise BenchmarkError("Researcher run has no successful raw result")

    costs = manifest.get("costs") or []
    for item in costs:
        if not isinstance(item, dict):
            raise BenchmarkError("each Researcher cost entry must be an object")
        amount = item.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            raise BenchmarkError("each Researcher cost entry needs a non-negative amount")
        if item.get("currency") != "USD" or not item.get("provider") or not item.get("basis"):
            raise BenchmarkError(
                "each Researcher paid call must record provider, USD currency, and basis"
            )
    reported_total = sum(
        float(item.get("amount", 0)) for item in costs
        if isinstance(item, dict) and isinstance(item.get("amount", 0), (int, float))
    )
    if reported_total > float(suite["budgets"]["researcher_max"]):
        raise BenchmarkError("Researcher reported cost exceeds the frozen USD 10 budget")
    prior_total = 0.0
    for other_id in EXPECTED_QUESTION_IDS:
        other = bundle_dir / "questions" / other_id / "researcher" / "snapshot.json"
        if other.is_file():
            prior_total += float(
                _read_json(other, "Researcher snapshot").get("reported_cost_total") or 0
            )
    if prior_total + reported_total > float(suite["budgets"]["researcher_max"]):
        raise BenchmarkError("Researcher cumulative reported cost exceeds the USD 10 budget")

    copied_root = destination / "run"
    copied = _copy_private_tree(run_dir, copied_root)
    scores = eval_harness.score_beast_dir(run_dir)
    receipt = {
        "schema_version": 1,
        "state": "completed",
        "question_id": question_id,
        "question_digest": hashlib.sha256(question["text"].encode("utf-8")).hexdigest(),
        "captured_at": _iso(timestamp),
        "source_run_digest": _digest_json({
            str(path.relative_to(run_dir)): _digest_file(path) for path in sorted(
                item for item in run_dir.rglob("*") if item.is_file()
            )
        }),
        "files": [_bundle_relative(bundle_dir, path) for path in copied],
        "answer_path": _bundle_relative(bundle_dir, copied_root / "synthesis.md"),
        "plan_path": _bundle_relative(bundle_dir, copied_root / "research-plan.md"),
        "manifest_path": _bundle_relative(bundle_dir, copied_root / "manifest.json"),
        "scores": scores,
        "duration_seconds": _duration_from_manifest(manifest),
        "reported_costs": costs,
        "reported_cost_total": reported_total,
        "validation": {
            "exact_question": True,
            "source_plan_present": True,
            "investigate_mode": True,
            "successful_raw_result": True,
            "max_drill_rounds": suite["researcher"]["max_drill_rounds"],
        },
    }
    write_private_json(receipt_path, receipt)
    _set_bundle_state(bundle_dir, "collecting")
    return receipt


def _attempt_summaries(bundle_dir, question_id):
    root = Path(bundle_dir) / "questions" / question_id / "parallel"
    attempts = []
    if not root.is_dir():
        return attempts
    for path in sorted(root.glob("attempt-*/attempt.json")):
        attempts.append(_read_json(path, "Parallel attempt"))
    return attempts


def _default_parallel_executor(question, processor):
    return eval_harness.run_parallel_task(question, processor=processor)


def _record_available_charge(outcome):
    """Add the provider-reported charge when the response exposes one.

    Parallel does not guarantee billing detail in every task result, so absence
    is recorded explicitly instead of substituting list price for an actual bill.
    """
    cost = dict(outcome.get("cost") or {})
    actual = cost.get("actual_charge")
    raw = outcome.get("raw_response")
    if actual is None and isinstance(raw, dict):
        candidates = (
            raw.get("cost"),
            (raw.get("usage") or {}).get("cost")
            if isinstance(raw.get("usage"), dict) else None,
            (raw.get("billing") or {}).get("amount")
            if isinstance(raw.get("billing"), dict) else None,
        )
        actual = next(
            (float(value) for value in candidates
             if isinstance(value, (int, float)) and not isinstance(value, bool)),
            None,
        )
    cost["actual_charge"] = actual
    cost["actual_charge_basis"] = (
        "provider task result" if actual is not None
        else "not exposed by the provider task result"
    )
    outcome = dict(outcome)
    outcome["cost"] = cost
    return outcome


def run_parallel(bundle_dir, question_id, *, confirm_paid=False,
                 retry_technical=False, executor=None, now=None):
    context = load_bundle(bundle_dir)
    suite = context["suite"]
    metadata = context["metadata"]
    question = _question(suite, question_id)
    bundle_dir = Path(bundle_dir)
    qdir = bundle_dir / "questions" / question_id
    snapshot_path = qdir / "researcher" / "snapshot.json"
    if not snapshot_path.is_file():
        raise BenchmarkError(f"Researcher snapshot for {question_id} must be frozen first")
    current = (now or _utc_now)()
    if current > _parse_time(metadata["deadline_at"]):
        raise BenchmarkError("the frozen 24-hour benchmark window has closed")
    attempts = _attempt_summaries(bundle_dir, question_id)
    if any(attempt.get("state") == "completed" for attempt in attempts):
        raise BenchmarkError(f"{question_id} already has a successful attempt; quality is not retryable")
    if attempts and attempts[-1].get("state") == "technical_failure" and not retry_technical:
        raise BenchmarkError("previous attempt failed technically; pass --retry-technical explicitly")
    if retry_technical and (not attempts or attempts[-1].get("state") != "technical_failure"):
        raise BenchmarkError("--retry-technical requires a preceding technical failure")

    preflight = _read_json(bundle_dir / "preflight.json", "preflight")
    price = suite["parallel"]["published_price"]
    completed_count = 0
    for qid in EXPECTED_QUESTION_IDS:
        completed_count += sum(
            attempt.get("state") == "completed"
            for attempt in _attempt_summaries(bundle_dir, qid)
        )
    if completed_count >= 5:
        raise BenchmarkError("Parallel five-successful-run budget is exhausted")
    preview = {
        "state": "preflight_only",
        "question_id": question_id,
        "question": question["text"],
        "processor": suite["parallel"]["processor"],
        "published_price": price["amount_per_successful_run"],
        "currency": price["currency"],
        "remaining_successful_run_budget": 5 - completed_count,
        "provider_available_at_init": bool(preflight["providers"].get("parallel")),
        "pricing_checked_for_live_run": bool(
            preflight.get("pricing_checked_for_live_run")
        ),
        "paid_call_made": False,
        "confirmation_required": True,
    }
    if not confirm_paid:
        return preview
    if not preflight["providers"].get("parallel"):
        raise BenchmarkError("Parallel was unavailable in the frozen preflight")
    if preflight.get("pricing_checked_for_live_run") is not True:
        raise BenchmarkError(
            "official Parallel pricing was not confirmed during preflight"
        )

    execute = executor or _default_parallel_executor
    outcome = execute(question["text"], suite["parallel"]["processor"])
    if not isinstance(outcome, dict):
        raise BenchmarkError("Parallel executor returned an invalid outcome")
    outcome = _record_available_charge(outcome)
    attempt_number = len(attempts) + 1
    attempt_dir = _ensure_private_dir(
        qdir / "parallel" / f"attempt-{attempt_number:03d}"
    )
    artifact_names = eval_harness.persist_parallel_artifacts(outcome, attempt_dir)
    state = "completed" if outcome.get("state") == "completed" else "technical_failure"
    summary = {
        "schema_version": 1,
        "question_id": question_id,
        "attempt_number": attempt_number,
        "attempt_path": _bundle_relative(bundle_dir, attempt_dir),
        "state": state,
        "technical_failure_reason": outcome.get("reason") if state != "completed" else None,
        "paid_confirmed_for_attempt": True,
        "run_id": outcome.get("run_id"),
        "started_at": outcome.get("started_at"),
        "finished_at": outcome.get("finished_at"),
        "duration_seconds": outcome.get("duration_seconds"),
        "processor": outcome.get("processor"),
        "cost": outcome.get("cost"),
        "scores": outcome.get("scores"),
        "artifacts": {
            name: _bundle_relative(bundle_dir, attempt_dir / relative)
            for name, relative in artifact_names.items()
        },
        "outcome_path": _bundle_relative(
            bundle_dir, attempt_dir / artifact_names["outcome"]
        ),
    }
    write_private_json(attempt_dir / "attempt.json", summary)
    if state == "completed":
        selected = {
            "attempt_number": attempt_number,
            "attempt_path": summary["attempt_path"],
            "answer_path": summary["artifacts"]["answer"],
            "outcome_path": summary["outcome_path"],
        }
        write_private_json(qdir / "parallel" / "selected.json", selected)
    _set_bundle_state(bundle_dir, "collecting")
    return summary


def _neutral_answer(text, label):
    lines = str(text).splitlines()
    for index, line in enumerate(lines):
        if line.strip():
            if line.lstrip().startswith("#"):
                lines.pop(index)
            break
    body = "\n".join(lines).strip()
    return f"# Answer {label}\n\n{body}\n"


def _blank_audit(question_id):
    answer = {
        "load_bearing_claims_checked": False,
        "citation_fit_checked": False,
        "freshness_checked": False,
        "unsupported_recommendations": [],
        "omissions": [],
        "contradictions": [],
        "critical_error": {
            "confirmed": False,
            "decision_changing": False,
            "evidence_note": "",
        },
    }
    return {
        "schema_version": 1,
        "question_id": question_id,
        "complete": False,
        "answers": {"A": dict(answer), "B": json.loads(json.dumps(answer))},
    }


def _blank_judgment(question_id):
    side = {"scores": {name: None for name in RUBRIC_DIMENSIONS}, "notes": ""}
    return {
        "schema_version": 1,
        "question_id": question_id,
        "complete": False,
        "blind_mapping_not_consulted": False,
        "answers": {"A": side, "B": json.loads(json.dumps(side))},
    }


def blind_question(bundle_dir, question_id, *, rng=None):
    context = load_bundle(bundle_dir)
    _question(context["suite"], question_id)
    bundle_dir = Path(bundle_dir)
    qdir = bundle_dir / "questions" / question_id
    snapshot = _read_json(
        qdir / "researcher" / "snapshot.json", "Researcher snapshot"
    )
    selected = _read_json(qdir / "parallel" / "selected.json", "Parallel selection")
    blind_dir = qdir / "blind"
    if blind_dir.exists():
        raise BenchmarkError(f"blind material for {question_id} already exists")
    _ensure_private_dir(blind_dir)
    researcher_answer = (bundle_dir / _assert_relative_path(snapshot["answer_path"])).read_text(
        encoding="utf-8"
    )
    parallel_answer = (bundle_dir / _assert_relative_path(selected["answer_path"])).read_text(
        encoding="utf-8"
    )
    rng = rng or random.SystemRandom()
    if rng.random() < 0.5:
        labels = {"A": "researcher", "B": "parallel"}
    else:
        labels = {"A": "parallel", "B": "researcher"}
    answers = {"researcher": researcher_answer, "parallel": parallel_answer}
    write_private_text(blind_dir / "answer-a.md", _neutral_answer(answers[labels["A"]], "A"))
    write_private_text(blind_dir / "answer-b.md", _neutral_answer(answers[labels["B"]], "B"))
    mapping = {
        "schema_version": 1,
        "question_id": question_id,
        "labels": labels,
        "note": "Private mapping. Do not open before owner scoring is complete.",
    }
    write_private_json(blind_dir / "mapping.json", mapping)
    write_private_json(blind_dir / "ai-audit.json", _blank_audit(question_id))
    write_private_json(blind_dir / "owner-judgment.json", _blank_judgment(question_id))
    receipt = {
        "question_id": question_id,
        "answer_a_path": _bundle_relative(bundle_dir, blind_dir / "answer-a.md"),
        "answer_b_path": _bundle_relative(bundle_dir, blind_dir / "answer-b.md"),
        "mapping_path": _bundle_relative(bundle_dir, blind_dir / "mapping.json"),
        "ai_audit_path": _bundle_relative(bundle_dir, blind_dir / "ai-audit.json"),
        "owner_judgment_path": _bundle_relative(
            bundle_dir, blind_dir / "owner-judgment.json"
        ),
    }
    write_private_json(blind_dir / "blind.json", receipt)
    if all(
        (bundle_dir / "questions" / qid / "blind" / "blind.json").is_file()
        for qid in EXPECTED_QUESTION_IDS
    ):
        _set_bundle_state(bundle_dir, "ready_for_review")
    else:
        _set_bundle_state(bundle_dir, "collecting")
    return receipt


def _validate_audit(audit):
    if audit.get("complete") is not True:
        raise BenchmarkError("AI audit is incomplete")
    for label in ("A", "B"):
        side = (audit.get("answers") or {}).get(label)
        if not isinstance(side, dict):
            raise BenchmarkError(f"AI audit is missing answer {label}")
        for field in (
            "load_bearing_claims_checked", "citation_fit_checked", "freshness_checked"
        ):
            if side.get(field) is not True:
                raise BenchmarkError(f"AI audit {label} did not complete {field}")
        for field in ("unsupported_recommendations", "omissions", "contradictions"):
            if not isinstance(side.get(field), list):
                raise BenchmarkError(f"AI audit {label}.{field} must be a list")
        critical = side.get("critical_error") or {}
        if not isinstance(critical.get("confirmed"), bool) or not isinstance(
            critical.get("decision_changing"), bool
        ):
            raise BenchmarkError(f"AI audit {label} has an invalid critical error")
        if critical["confirmed"] and critical["decision_changing"] and not str(
            critical.get("evidence_note") or ""
        ).strip():
            raise BenchmarkError(f"AI audit {label} critical error needs an evidence note")


def _judgment_totals(judgment):
    if judgment.get("complete") is not True:
        raise BenchmarkError("owner judgment is incomplete")
    if judgment.get("blind_mapping_not_consulted") is not True:
        raise BenchmarkError("owner judgment must confirm the mapping stayed closed")
    totals = {}
    for label in ("A", "B"):
        scores = ((judgment.get("answers") or {}).get(label) or {}).get("scores")
        if not isinstance(scores, dict) or set(scores) != set(RUBRIC_DIMENSIONS):
            raise BenchmarkError(f"owner judgment {label} is missing rubric dimensions")
        for dimension in RUBRIC_DIMENSIONS:
            value = scores[dimension]
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
                raise BenchmarkError(
                    f"owner judgment {label}.{dimension} must be an integer from 0 to 4"
                )
        totals[label] = sum(scores.values())
    return totals


def derive_question_result(bundle_dir, question_id):
    context = load_bundle(bundle_dir)
    suite = context["suite"]
    _question(suite, question_id)
    bundle_dir = Path(bundle_dir)
    qdir = bundle_dir / "questions" / question_id
    mapping = _read_json(qdir / "blind" / "mapping.json", "blind mapping")
    audit = _read_json(qdir / "blind" / "ai-audit.json", "AI audit")
    judgment = _read_json(qdir / "blind" / "owner-judgment.json", "owner judgment")
    _validate_audit(audit)
    totals = _judgment_totals(judgment)
    margin = abs(totals["A"] - totals["B"])
    winner_label = "tie"
    if margin >= suite["rules"]["per_question_win_margin"]:
        winner_label = "A" if totals["A"] > totals["B"] else "B"
    if winner_label != "tie":
        critical = audit["answers"][winner_label]["critical_error"]
        if critical["confirmed"] and critical["decision_changing"]:
            winner_label = "tie"
    labels = mapping.get("labels") or {}
    if set(labels) != {"A", "B"} or set(labels.values()) != {"researcher", "parallel"}:
        raise BenchmarkError("blind mapping is invalid")
    winner = labels[winner_label] if winner_label in ("A", "B") else "tie"

    researcher = _read_json(
        qdir / "researcher" / "snapshot.json", "Researcher snapshot"
    )
    selected = _read_json(qdir / "parallel" / "selected.json", "Parallel selection")
    outcome = _read_json(bundle_dir / _assert_relative_path(selected["outcome_path"]),
                         "Parallel outcome")
    return {
        "question_id": question_id,
        "quality_totals": totals,
        "margin": margin,
        "winner_label": winner_label,
        "winner": winner,
        "objective_metrics": {
            "researcher": researcher.get("scores"),
            "parallel": outcome.get("scores"),
        },
        "economics": {
            "researcher_reported_cost": researcher.get("reported_cost_total"),
            "researcher_duration_seconds": researcher.get("duration_seconds"),
            "parallel_list_cost": (outcome.get("cost") or {}).get("amount"),
            "parallel_actual_charge": (outcome.get("cost") or {}).get("actual_charge"),
            "parallel_duration_seconds": outcome.get("duration_seconds"),
        },
    }


def _report_markdown(report):
    lines = [
        "# Researcher vs Parallel — Internal Benchmark",
        "",
        f"Overall result: **{report['overall']['winner']}**",
        "",
        "| Question | Winner | A | B | Margin |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in report["questions"]:
        lines.append(
            f"| {result['question_id']} | {result['winner']} | "
            f"{result['quality_totals']['A']} | {result['quality_totals']['B']} | "
            f"{result['margin']} |"
        )
    lines.extend([
        "",
        "## Cost and time (not part of quality score)",
        "",
        f"- Parallel list cost: USD {report['economics']['parallel_list_cost']:.2f}",
        f"- Parallel duration: {report['economics']['parallel_duration_seconds']:.1f} seconds",
        f"- Researcher reported cost: USD {report['economics']['researcher_reported_cost']:.2f}",
        f"- Researcher duration: {report['economics']['researcher_duration_seconds']:.1f} seconds",
        "",
        "Internal only. No publication or merge is authorized by this report.",
    ])
    return "\n".join(lines) + "\n"


def build_report(bundle_dir):
    context = load_bundle(bundle_dir)
    suite = context["suite"]
    bundle_dir = Path(bundle_dir)
    results = []
    for question in suite["questions"]:
        try:
            results.append(derive_question_result(bundle_dir, question["id"]))
        except BenchmarkError as exc:
            raise BenchmarkError(f"{question['id']}: {exc}") from exc
    wins = {"researcher": 0, "parallel": 0, "tie": 0}
    for result in results:
        wins[result["winner"]] += 1
    required = suite["rules"]["overall_wins_required"]
    if wins["researcher"] >= required:
        overall = "researcher"
    elif wins["parallel"] >= required:
        overall = "parallel"
    else:
        overall = "tie"
    economics = {
        "parallel_list_cost": sum(
            float(result["economics"]["parallel_list_cost"] or 0) for result in results
        ),
        "parallel_duration_seconds": sum(
            float(result["economics"]["parallel_duration_seconds"] or 0)
            for result in results
        ),
        "researcher_reported_cost": sum(
            float(result["economics"]["researcher_reported_cost"] or 0)
            for result in results
        ),
        "researcher_duration_seconds": sum(
            float(result["economics"]["researcher_duration_seconds"] or 0)
            for result in results
        ),
    }
    report = {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "generated_at": _iso(_utc_now()),
        "overall": {"winner": overall, "wins": wins},
        "questions": results,
        "economics": economics,
        "quality_note": "Cost and elapsed time are reported separately and never alter quality totals.",
        "publication": "internal_only",
    }
    write_private_json(bundle_dir / "report.json", report)
    write_private_text(bundle_dir / "report.md", _report_markdown(report))
    metadata = context["metadata"]
    metadata["state"] = "complete"
    metadata["report_path"] = "report.json"
    write_private_json(bundle_dir / "bundle.json", metadata)
    return report


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="freeze suite and offline preflight")
    init.add_argument("--suite", default=str(DEFAULT_SUITE))
    init.add_argument("--bundle", default=None)
    init.add_argument(
        "--confirm-price-checked", action="store_true",
        help="record that the operator re-opened the official price and processor pages; authorizes no paid call",
    )

    snapshot = sub.add_parser("snapshot-researcher", help="freeze one completed run")
    snapshot.add_argument("--bundle", required=True)
    snapshot.add_argument("--question", required=True, choices=EXPECTED_QUESTION_IDS)
    snapshot.add_argument("--run-dir", required=True)
    snapshot.add_argument(
        "--technical-failure-reason", default=None,
        help="preserve an incomplete technical attempt before a retry; completed or merely poor answers are rejected",
    )

    parallel = sub.add_parser("run-parallel", help="preflight or run one Ultra attempt")
    parallel.add_argument("--bundle", required=True)
    parallel.add_argument("--question", required=True, choices=EXPECTED_QUESTION_IDS)
    parallel.add_argument("--confirm-paid", action="store_true")
    parallel.add_argument("--retry-technical", action="store_true")

    blind = sub.add_parser("blind", help="create private A/B review material")
    blind.add_argument("--bundle", required=True)
    blind.add_argument("--question", required=True, choices=EXPECTED_QUESTION_IDS)

    report = sub.add_parser("report", help="derive the complete five-question result")
    report.add_argument("--bundle", required=True)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_bundle(
                args.suite, args.bundle,
                price_checked=args.confirm_price_checked,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "snapshot-researcher":
            result = snapshot_researcher(
                args.bundle, args.question, args.run_dir,
                technical_failure_reason=args.technical_failure_reason,
            )
        elif args.command == "run-parallel":
            result = run_parallel(
                args.bundle, args.question,
                confirm_paid=args.confirm_paid,
                retry_technical=args.retry_technical,
            )
            if not args.confirm_paid:
                print("NO PAID CALL MADE — pass --confirm-paid only after explicit approval.")
        elif args.command == "blind":
            result = blind_question(args.bundle, args.question)
        else:
            result = build_report(args.bundle)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BenchmarkError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
