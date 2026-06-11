"""Run MMLongBench-Doc benchmark arms."""

from __future__ import annotations

import argparse
import asyncio
import ast
import json
import os
import random
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .agent import create_benchmark_agent
from .dataset import filter_questions_for_available_docs
from .metrics import collect_metrics, extract_structured_response, iter_messages
from .prompts import question_prompt
from .schemas import schema_for_answer_format, structured_to_prediction
from .judge import build_judge, resolve_score
from .staging import cleanup_staged_corpus, doc_folders_for_questions, stage_corpus


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.toml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str))
        f.write("\n")


def parse_list_field(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (SyntaxError, ValueError):
            return [value]
    return [] if value in {None, ""} else [value]


def is_multimodal(row: dict[str, Any]) -> bool:
    sources = [str(source).lower() for source in parse_list_field(row.get("evidence_sources"))]
    return any("pure-text" not in source and "plain-text" not in source for source in sources)


def select_questions(
    questions: list[dict[str, Any]],
    *,
    tier: str,
    tiers: dict[str, int],
    seed: int,
    limit: int | None,
    include_unanswerable: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows = list(questions)
    rng.shuffle(rows)

    if tier == "full":
        selected = rows
    else:
        tier_size = tiers.get(tier)
        if tier_size is None:
            raise ValueError(f"Unknown tier: {tier}")
        size = limit or tier_size
        answerable = [row for row in rows if row.get("answer") != "Not answerable"]
        multimodal = [row for row in answerable if is_multimodal(row)]
        rest = [row for row in answerable if row not in multimodal]
        selected = (multimodal + rest)[:size]

    if not include_unanswerable:
        selected = [row for row in selected if row.get("answer") != "Not answerable"]
    if limit is not None and tier == "full":
        selected = selected[:limit]
    return selected


def last_message_text(run_output: Any) -> str:
    messages = iter_messages(run_output)
    if not messages:
        return ""
    content = getattr(messages[-1], "content", None)
    if content is None and isinstance(messages[-1], dict):
        content = messages[-1].get("content")
    return str(content or "").strip()


async def run_question(
    *,
    arm: str,
    question: dict[str, Any],
    corpus_dir: Path,
    agent_config: dict[str, Any],
    mdvision_server: Path,
    run_id: str,
    judge: Any | None = None,
) -> dict[str, Any]:
    doc_id = str(question["doc_id"])
    doc_folder = Path(doc_id).stem
    answer_format = str(question.get("answer_format", "Str"))
    response_format = schema_for_answer_format(answer_format)

    agent = await create_benchmark_agent(
        arm=arm,  # type: ignore[arg-type]
        corpus_dir=corpus_dir,
        agent_config=agent_config,
        response_format=response_format,
        mdvision_server=mdvision_server,
    )

    started = time.perf_counter()
    error = None
    run_output: Any = {}
    try:
        run_output = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": question_prompt(doc_folder, str(question["question"])),
                    }
                ]
            },
            config={
                "configurable": {"thread_id": f"{run_id}:{arm}:{question['question_id']}"},
                "recursion_limit": int(agent_config.get("max_iterations", 100)),
            },
        )
    except Exception as exc:  # noqa: BLE001 - failures are benchmark data.
        error = str(exc)

    latency_s = time.perf_counter() - started
    structured = extract_structured_response(run_output)
    pred = structured_to_prediction(structured)
    if pred == "Fail to answer" and error is None:
        pred = last_message_text(run_output) or pred

    scoring = await resolve_score(
        gt=question["answer"],
        pred=pred,
        answer_type=answer_format,
        question=str(question["question"]),
        judge=judge,
    )
    metrics = collect_metrics(run_output)

    return {
        "run_id": run_id,
        "arm": arm,
        "question_id": question["question_id"],
        "doc_id": doc_id,
        "doc_type": question.get("doc_type"),
        "question": question["question"],
        "answer": question["answer"],
        "pred": pred,
        "answer_format": answer_format,
        "evidence_pages": question.get("evidence_pages"),
        "evidence_sources": question.get("evidence_sources"),
        **scoring,
        "latency_s": latency_s,
        "error": error,
        **metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--arm", choices=["baseline", "mdvision", "both"], default="baseline")
    parser.add_argument("--tier", choices=["smoke", "pilot", "standard", "full"], default="smoke")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-unanswerable", action="store_true")
    parser.add_argument("--questions-file", type=Path, default=None)
    parser.add_argument("--corpus-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-judge", action="store_true", help="Disable LLM semantic judge fallback.")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    config = load_config(args.config)
    paths_cfg = config["paths"]
    agent_config = dict(config["agent"])
    if args.model:
        agent_config["model"] = args.model

    judge_config = dict(config.get("judge", {}))
    if args.no_judge:
        judge_config["enabled"] = False
    judge = build_judge(judge_config)

    questions_file = (args.questions_file or ROOT / paths_cfg["raw_dir"] / "questions.jsonl").resolve()
    documents_dir = (ROOT / paths_cfg["documents_dir"]).resolve()
    source_corpus_dir = (args.corpus_dir or ROOT / paths_cfg["corpus_dir"]).resolve()
    results_root = (args.results_dir or ROOT / paths_cfg["results_dir"]).resolve()
    mdvision_server = (ROOT / paths_cfg["mdvision_server"]).resolve()

    all_questions = read_jsonl(questions_file)
    questions, availability = filter_questions_for_available_docs(
        all_questions,
        documents_dir=documents_dir,
        corpus_dir=source_corpus_dir,
    )
    if not questions:
        raise SystemExit(
            "No questions remain after filtering to downloaded PDFs with converted corpus. "
            "Run download_data.py and convert_pdfs.py first."
        )
    if availability["excluded_missing_pdf"] or availability["excluded_missing_corpus"]:
        print(
            "Filtered questions to available docs: "
            f"kept {availability['questions_kept']}/{availability['questions_total']} "
            f"(missing PDF: {availability['excluded_missing_pdf']}, "
            f"missing corpus: {availability['excluded_missing_corpus']})"
        )

    selected = select_questions(
        questions,
        tier=args.tier,
        tiers=config["tiers"],
        seed=args.seed,
        limit=args.limit,
        include_unanswerable=args.include_unanswerable,
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    doc_folders = doc_folders_for_questions(selected)
    staged_corpus_dir = stage_corpus(source_corpus_dir, run_id, doc_folders)

    arms = ["baseline", "mdvision"] if args.arm == "both" else [args.arm]
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "arm": args.arm,
        "arms": arms,
        "tier": args.tier,
        "seed": args.seed,
        "question_count": len(selected),
        "document_folder_count": len(doc_folders),
        "model": agent_config["model"],
        "service_tier": agent_config.get("service_tier"),
        "reasoning_effort": agent_config.get("reasoning_effort"),
        "judge": {
            "enabled": judge is not None,
            "model": judge_config.get("model") if judge is not None else None,
            "threshold": judge_config.get("threshold", 1.0),
            "service_tier": judge_config.get("service_tier"),
        },
        "questions_file": str(questions_file),
        "question_filter": availability,
        "source_corpus_dir": str(source_corpus_dir),
        "staged_corpus_dir": str(staged_corpus_dir),
        "mdvision_server": str(mdvision_server),
        "git_sha": os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or None,
    }
    write_json(run_dir / "run_manifest.json", manifest)

    try:
        for arm in arms:
            output_path = run_dir / f"{arm}.jsonl"
            for i, question in enumerate(selected, start=1):
                row = await run_question(
                    arm=arm,
                    question=question,
                    corpus_dir=staged_corpus_dir,
                    agent_config=agent_config,
                    mdvision_server=mdvision_server,
                    run_id=run_id,
                    judge=judge,
                )
                append_jsonl(output_path, row)
                judge_note = ""
                if row.get("judge_used"):
                    judge_note = f" judge={'yes' if row.get('judge_equivalent') else 'no'}"
                print(
                    f"{arm} {i}/{len(selected)} q={row['question_id']} "
                    f"score={row['score']:.3f} anls={row['score_anls']:.3f}{judge_note}"
                )
    finally:
        cleanup_staged_corpus(run_id)

    latest = results_root / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_dir, target_is_directory=True)
    except OSError:
        pass

    print(f"Results: {run_dir}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
