"""Aggregate benchmark JSONL outputs into a markdown report."""

from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .scoring import eval_acc_and_f1


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def parse_sources(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (SyntaxError, ValueError):
            pass
    return [str(value)] if value else []


def summarize_arm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    acc, f1 = eval_acc_and_f1(rows)
    judged = [row for row in rows if row.get("judge_used")]
    upgraded = [row for row in judged if row.get("judge_equivalent")]
    return {
        "n": len(rows),
        "accuracy": acc,
        "f1": f1,
        "accuracy_anls": mean(row.get("score_anls", row.get("score", 0)) for row in rows) if rows else 0.0,
        "judge_invocations": len(judged),
        "judge_upgrades": len(upgraded),
        "avg_tool_calls": mean(row.get("tool_calls_total", 0) for row in rows) if rows else 0.0,
        "avg_input_tokens": mean(row.get("input_tokens", 0) for row in rows) if rows else 0.0,
        "avg_output_tokens": mean(row.get("output_tokens", 0) for row in rows) if rows else 0.0,
        "avg_latency_s": mean(row.get("latency_s", 0.0) for row in rows) if rows else 0.0,
    }


def collect_by_arm(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(run_dir.glob("*.jsonl")):
        by_arm[path.stem] = read_jsonl(path)
    return by_arm


def evidence_breakdown(rows: list[dict[str, Any]]) -> dict[str, tuple[float, int]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for source in parse_sources(row.get("evidence_sources")):
            groups[source].append(row)
    return {source: (eval_acc_and_f1(group)[0], len(group)) for source, group in groups.items()}


def format_float(value: float) -> str:
    return f"{value:.3f}"


def build_report(run_dir: Path) -> str:
    by_arm = collect_by_arm(run_dir)
    lines = [f"# Benchmark Report: `{run_dir.name}`", ""]

    lines.extend(
        [
            "## Overall",
            "",
            "| Arm | N | Accuracy | F1 | ANLS acc | Judge calls | Judge upgrades | Avg tool calls | Avg input tokens | Avg output tokens | Avg latency s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for arm, rows in by_arm.items():
        summary = summarize_arm(rows)
        lines.append(
            "| {arm} | {n} | {accuracy} | {f1} | {accuracy_anls} | {judge_invocations} | {judge_upgrades} | {tools} | {input_tokens} | {output_tokens} | {latency} |".format(
                arm=arm,
                n=summary["n"],
                accuracy=format_float(summary["accuracy"]),
                f1=format_float(summary["f1"]),
                accuracy_anls=format_float(summary["accuracy_anls"]),
                judge_invocations=summary["judge_invocations"],
                judge_upgrades=summary["judge_upgrades"],
                tools=format_float(summary["avg_tool_calls"]),
                input_tokens=format_float(summary["avg_input_tokens"]),
                output_tokens=format_float(summary["avg_output_tokens"]),
                latency=format_float(summary["avg_latency_s"]),
            )
        )

    if "baseline" in by_arm and "mdvision" in by_arm:
        base = summarize_arm(by_arm["baseline"])
        mdv = summarize_arm(by_arm["mdvision"])
        lines.extend(
            [
                "",
                "## Delta",
                "",
                f"- Accuracy: {format_float(mdv['accuracy'] - base['accuracy'])}",
                f"- F1: {format_float(mdv['f1'] - base['f1'])}",
                f"- ANLS accuracy: {format_float(mdv['accuracy_anls'] - base['accuracy_anls'])}",
                f"- Judge upgrades: {mdv['judge_upgrades'] - base['judge_upgrades']}",
                f"- Avg tool calls: {format_float(mdv['avg_tool_calls'] - base['avg_tool_calls'])}",
                f"- Avg input tokens: {format_float(mdv['avg_input_tokens'] - base['avg_input_tokens'])}",
                f"- Avg output tokens: {format_float(mdv['avg_output_tokens'] - base['avg_output_tokens'])}",
            ]
        )

    lines.extend(["", "## Evidence Sources", ""])
    for arm, rows in by_arm.items():
        lines.extend(
            [
                f"### {arm}",
                "",
                "| Evidence source | N | Accuracy |",
                "|---|---:|---:|",
            ]
        )
        for source, (acc, count) in sorted(evidence_breakdown(rows).items()):
            lines.append(f"| {source} | {count} | {format_float(acc)} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "results" / "latest")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    report = build_report(run_dir)
    output = args.output or run_dir / "report.md"
    output.write_text(report, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
