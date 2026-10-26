"""Offline scoring for Family A.

Scoring runs *after* generation, on frozen artefacts. It never touches a live
session, and it never feeds anything back to the model.

Metrics
-------
``acc``            accuracy of the model's rule on the held-out inputs, against
                   the true labels. The headline number.
``trap_escaped``   the model's rule disagrees with the surface rule somewhere on
                   the held-out inputs. ``acc`` near 1.0 means the trap was
                   escaped; ``acc`` near the surface rule's expected accuracy
                   means it was not.
``spec_ok``        the model's rule satisfies the spec.
``identical_true`` the model's rule is functionally identical to the true rule
                   over the whole domain (stronger than ``acc``).
``considered_trap`` the surface rule appears among the alternatives the model
                   says it considered — i.e. it generated the obvious answer and
                   then rejected it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .rules import RuleSpec
from .safe_eval import RuleError, compile_rule, equivalent


@dataclass
class Response:
    """One model answer."""

    instance_id: str
    rule: str
    alternatives: List[str] = field(default_factory=list)
    why: str = ""
    spec_used: List[str] = field(default_factory=list)
    run: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "Response":
        alternatives = data.get("alternatives") or []
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        spec_used = data.get("spec_used") or []
        if isinstance(spec_used, str):
            spec_used = [spec_used]
        return cls(
            instance_id=data.get("instance_id", ""),
            rule=data.get("rule", "") or "",
            alternatives=[str(item) for item in alternatives],
            why=str(data.get("why", "") or ""),
            spec_used=[str(item) for item in spec_used],
            run=str(data.get("run", "") or ""),
        )


@dataclass
class Score:
    """Scores for one instance."""

    instance_id: str
    rule_valid: bool
    error: Optional[str]
    acc: Optional[float]
    trap_escaped: Optional[bool]
    spec_ok: Optional[bool]
    identical_true: Optional[bool]
    considered_trap: Optional[bool]
    surface_acc: Optional[float]
    well_posed: bool
    spec_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "rule_valid": self.rule_valid,
            "error": self.error,
            "acc": self.acc,
            "trap_escaped": self.trap_escaped,
            "spec_ok": self.spec_ok,
            "identical_true": self.identical_true,
            "considered_trap": self.considered_trap,
            "surface_acc": self.surface_acc,
            "well_posed": self.well_posed,
            "spec_name": self.spec_name,
        }


def _predict(rule, inputs: Sequence[Dict[str, int]]) -> Optional[List[Any]]:
    values: List[Any] = []
    for point in inputs:
        try:
            values.append(rule(point["a"], point["b"], 0))
        except RuleError:
            return None
    return values


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return left == right


def score_instance(
    visible: Dict,
    key: Dict,
    response: Response,
    spec: RuleSpec,
    domain_points: Sequence[Sequence[int]],
) -> Score:
    heldout_inputs = visible["heldout_inputs"]
    labels = key["heldout_labels"]
    surface_acc = key.get("surface_acc")

    try:
        rule = compile_rule(response.rule)
    except RuleError as exc:
        return Score(
            instance_id=visible.get("instance_id", ""),
            rule_valid=False,
            error=str(exc),
            acc=None,
            trap_escaped=None,
            spec_ok=None,
            identical_true=None,
            considered_trap=None,
            surface_acc=surface_acc,
            well_posed=key.get("well_posed", False),
            spec_name=spec.name,
        )

    predictions = _predict(rule, heldout_inputs)
    if predictions is None:
        return Score(
            instance_id=visible.get("instance_id", ""),
            rule_valid=True,
            error="rule failed on a held-out input",
            acc=None,
            trap_escaped=None,
            spec_ok=None,
            identical_true=None,
            considered_trap=None,
            surface_acc=surface_acc,
            well_posed=key.get("well_posed", False),
            spec_name=spec.name,
        )

    correct = sum(
        1 for prediction, label in zip(predictions, labels) if _equal(prediction, label["y"])
    )
    acc = correct / len(labels) if labels else None

    try:
        surface_rule = compile_rule(key["surface_expr"])
        surface_predictions = _predict(surface_rule, heldout_inputs) or []
        trap_escaped = any(
            not _equal(mine, theirs)
            for mine, theirs in zip(predictions, surface_predictions)
        )
    except RuleError:
        trap_escaped = None

    try:
        spec_ok = spec.check(rule)
    except RuleError:
        spec_ok = False

    try:
        true_rule = compile_rule(key["true_expr"])
        identical_true = equivalent(rule, true_rule, [(a, b) for a, b in domain_points])
    except RuleError:
        identical_true = False

    considered_trap = False
    try:
        surface_rule = compile_rule(key["surface_expr"])
        for alternative in response.alternatives:
            try:
                candidate = compile_rule(alternative)
            except RuleError:
                continue
            if equivalent(candidate, surface_rule, [(a, b) for a, b in domain_points]):
                considered_trap = True
                break
    except RuleError:
        considered_trap = False

    return Score(
        instance_id=visible.get("instance_id", ""),
        rule_valid=True,
        error=None,
        acc=acc,
        trap_escaped=trap_escaped,
        spec_ok=spec_ok,
        identical_true=identical_true,
        considered_trap=considered_trap,
        surface_acc=surface_acc,
        well_posed=key.get("well_posed", False),
        spec_name=spec.name,
    )


def aggregate(scores: Sequence[Score]) -> Dict[str, Any]:
    def mean(values: Sequence[Optional[float]]) -> Optional[float]:
        present = [v for v in values if v is not None]
        return sum(present) / len(present) if present else None

    def rate(values: Sequence[Optional[bool]]) -> Optional[float]:
        present = [v for v in values if v is not None]
        return sum(1 for v in present if v) / len(present) if present else None

    return {
        "n": len(scores),
        "n_valid": sum(1 for s in scores if s.rule_valid),
        "mean_acc": mean([s.acc for s in scores]),
        "trap_escape_rate": rate([s.trap_escaped for s in scores]),
        "spec_ok_rate": rate([s.spec_ok for s in scores]),
        "identical_true_rate": rate([s.identical_true for s in scores]),
        "considered_trap_rate": rate([s.considered_trap for s in scores]),
        "mean_surface_acc": mean([s.surface_acc for s in scores]),
    }


def load_responses(path: str) -> List[Response]:
    """Load a responses file.

    Accepts a list of response objects, a mapping of instance id to a single
    response, or a mapping of instance id to a list of responses (one per run).
    """
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    responses: List[Response] = []
    if isinstance(raw, dict):
        if "responses" in raw and isinstance(raw["responses"], list):
            raw = raw["responses"]
        else:
            for key, value in raw.items():
                if isinstance(value, list):
                    for item in value:
                        item = dict(item)
                        item.setdefault("instance_id", key)
                        responses.append(Response.from_dict(item))
                else:
                    value = dict(value)
                    value.setdefault("instance_id", key)
                    responses.append(Response.from_dict(value))
            return responses
    for item in raw:
        responses.append(Response.from_dict(item))
    return responses
