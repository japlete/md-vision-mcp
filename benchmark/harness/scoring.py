"""MMLongBench-Doc scoring helpers.

Derived from MMLongBench-Doc `eval/eval_score.py` (Apache-2.0). This version
removes debug prints and uses `ast.literal_eval` for list parsing.
"""

from __future__ import annotations

import ast
import re
from math import isclose
from typing import Any


NOT_ANSWERABLE = "Not answerable"
FAIL_TO_ANSWER = "Fail to answer"


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min(distances[i1], distances[i1 + 1], distances_[-1]))
        distances = distances_
    return distances[-1]


def anls_compute(groundtruth: str, prediction: str, threshold: float = 0.5) -> float:
    dist = levenshtein_distance(groundtruth, prediction)
    length = max(len(groundtruth.upper()), len(prediction.upper()))
    value = 0.0 if length == 0 else float(dist) / float(length)
    anls = 1.0 - value
    return 0.0 if anls <= threshold else anls


def is_float_equal(
    reference: Any,
    prediction: Any,
    include_percentage: bool = False,
    is_close: bool = False,
) -> bool:
    def get_precision(gt_ans: float) -> int:
        precision = 3
        if "." in str(gt_ans):
            precision = len(str(gt_ans).split(".")[-1])
        return precision

    reference = float(str(reference).strip().rstrip("%").strip())
    try:
        prediction = float(str(prediction).strip().rstrip("%").strip())
    except Exception:
        return False

    gt_result = [reference / 100, reference, reference * 100] if include_percentage else [reference]
    for item in gt_result:
        try:
            if is_close and isclose(item, prediction, rel_tol=0.01):
                return True
            precision = max(min(get_precision(prediction), get_precision(item)), 2)
            if round(prediction, precision) == round(item, precision):
                return True
        except Exception:
            continue
    return False


def get_clean_string(s: Any) -> str:
    value = str(s).lower().strip()
    for suffix in ("mile", "miles", "million"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].strip()
    value = re.sub(r"\s*\([^)]*\)", "", value).strip()
    value = re.sub(r"^['\"]|['\"]$", "", value).strip()
    value = value.strip().lstrip("$").strip()
    value = value.strip().rstrip("%").strip()
    return value


def is_exact_match(s: str) -> bool:
    if "https://" in s:
        return True
    if s.endswith(".py") or s.endswith("ipynb"):
        return True
    if s.startswith("page"):
        return True
    if re.fullmatch(r"\b\d+(-\d+|\s\d+)?\b", s):
        return True
    if "a.m." in s or "p.m." in s:
        return True
    if re.fullmatch(r"\b\d{4}[-\s]\d{2}[-\s]\d{2}\b", s):
        return True
    if re.fullmatch(r"\b\d{4}[-\s]\d{2}\b", s):
        return True
    return bool(re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", s))


def isfloat(num: Any) -> bool:
    try:
        float(num)
        return True
    except (TypeError, ValueError):
        return False


def parse_possible_list(value: Any) -> list[Any]:
    if isinstance(value, str) and value.startswith("["):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            pass
    return value if isinstance(value, list) else [value]


def eval_score(gt: Any, pred: Any, answer_type: str) -> float:
    if gt == NOT_ANSWERABLE:
        return float(pred == NOT_ANSWERABLE)

    if answer_type == "Int":
        try:
            gt_int, pred_int = int(gt), int(float(pred))
        except Exception:
            pred_int = ""
            gt_int = gt
        score: bool | float = gt_int == pred_int
    elif answer_type == "Float":
        try:
            gt_float = float(get_clean_string(str(gt)))
            pred_float = float(get_clean_string(str(pred)))
        except Exception:
            pred_float = ""
            gt_float = gt
        score = is_float_equal(gt_float, pred_float, include_percentage=True, is_close=True)
    elif answer_type in ["Str", "None"]:
        gt_str = get_clean_string(gt)
        pred_str = get_clean_string(pred)
        score = gt_str == pred_str if is_exact_match(gt_str) else anls_compute(gt_str, pred_str)
    else:
        gt_list = parse_possible_list(gt)
        pred_list = parse_possible_list(pred)
        if len(gt_list) != len(pred_list):
            score = 0.0
        else:
            gt_clean = sorted(get_clean_string(a) for a in gt_list)
            pred_clean = sorted(get_clean_string(a) for a in pred_list)
            if not gt_clean:
                score = 1.0
            elif isfloat(gt_clean[0]) or is_exact_match(gt_clean[0]):
                score = "-".join(gt_clean) == "-".join(pred_clean)
            else:
                score = min(anls_compute(gt_v, pred_v) for gt_v, pred_v in zip(gt_clean, pred_clean))

    return float(score)


def eval_acc_and_f1(samples: list[dict[str, Any]]) -> tuple[float, float]:
    evaluated_samples = [sample for sample in samples if "score" in sample]
    if not evaluated_samples:
        return 0.0, 0.0

    acc = sum(sample["score"] for sample in evaluated_samples) / len(evaluated_samples)
    try:
        answerable = [sample for sample in evaluated_samples if sample["answer"] != NOT_ANSWERABLE]
        predicted_answerable = [sample for sample in evaluated_samples if sample["pred"] != NOT_ANSWERABLE]
        recall = sum(sample["score"] for sample in answerable) / len(answerable)
        precision = sum(sample["score"] for sample in answerable) / len(predicted_answerable)
        f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0.0 else 0.0
    except Exception:
        f1 = 0.0

    return acc, f1
