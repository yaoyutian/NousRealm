"""Instance generation for Family A (格竹).

Every instance is generated procedurally from a seed, so it is novel by
construction and cannot be retrieved from anywhere. This is the single most
important property of the family: if instances were drawn from an existing
dataset, a model that recognises the dataset would be scoring as (b) implicit
retrieval rather than as (a).

Generation is rejection sampling:

1. draw a true rule ``R`` and a surface rule ``S``;
2. find a spec that ``R`` satisfies and ``S`` violates;
3. compute the **agreement set** ``A`` — the inputs where ``R`` and ``S`` give
   the same answer;
4. draw the training examples from ``A``, so the surface rule fits perfectly;
5. draw the held-out inputs from ``A`` and from its complement, so the surface
   rule is wrong on exactly the part the model has never seen agreement for;
6. check that the library pins the answer down (solvability), and that the
   training examples do not trivially reveal the slice they came from.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .rules import (
    RuleTemplate,
    SPEC_BY_NAME,
    TRUE_POOL,
    TRAP_POOL,
    Rule,
    RuleSpec,
    discriminating_spec,
    fits_examples,
    library_solutions,
)


@dataclass
class Instance:
    """A generated task instance."""

    instance_id: str
    seed: int
    domain: List[int]
    spec_name: str
    true_rule_name: str
    true_expr: str
    surface_rule_name: str
    surface_expr: str
    training: List[Dict[str, int]]
    heldout_inputs: List[Dict[str, int]]
    agreement_points: List[Tuple[int, int]]
    library_solutions: List[str] = field(default_factory=list)
    well_posed: bool = True

    def spec(self) -> RuleSpec:
        return SPEC_BY_NAME[self.spec_name]

    def visible(self) -> Dict:
        """The part handed to the model."""
        spec = self.spec()
        return {
            "instance_id": self.instance_id,
            "domain": self.domain,
            "spec": {"name": spec.name, "text": spec.text_en},
            "spec_text_zh": spec.text_zh,
            "training": self.training,
            "heldout_inputs": self.heldout_inputs,
            "response_format": {
                "rule": "a single expression over a and b, e.g. '(a + b) % 2'",
                "alternatives": "list of other candidate rules you considered and rejected",
                "why": "why this rule and not the alternatives",
                "spec_used": "list of spec clauses you applied",
            },
        }

    def key(self) -> Dict:
        """The part never shown to the model."""
        true_rule = _compile(self.true_expr)
        labels = [
            {"a": point["a"], "b": point["b"], "y": true_rule(point["a"], point["b"], 0)}
            for point in self.heldout_inputs
        ]
        surface_rule = _compile(self.surface_expr)
        surface_acc = (
            sum(
                1
                for point, label in zip(self.heldout_inputs, labels)
                if surface_rule(point["a"], point["b"], 0) == label["y"]
            )
            / len(labels)
            if labels
            else None
        )
        return {
            "instance_id": self.instance_id,
            "true_rule_name": self.true_rule_name,
            "true_expr": self.true_expr,
            "surface_rule_name": self.surface_rule_name,
            "surface_expr": self.surface_expr,
            "heldout_labels": labels,
            "surface_acc": surface_acc,
            "agreement_points": [list(point) for point in self.agreement_points],
            "library_solutions": self.library_solutions,
            "well_posed": self.well_posed,
        }


def _compile(expr: str) -> Rule:
    from .safe_eval import compile_rule

    return compile_rule(expr)


def _domain(size: int) -> List[int]:
    return list(range(size))


def _agreement_points(
    true_rule: Rule, surface_rule: Rule, domain: Sequence[int]
) -> List[Tuple[int, int]]:
    points: List[Tuple[int, int]] = []
    for a in domain:
        for b in domain:
            if true_rule(a, b, 0) == surface_rule(a, b, 0):
                points.append((a, b))
    return points


def generate_instance(
    seed: int,
    domain_size: int = 10,
    train_size: int = 12,
    heldout_size: int = 20,
    heldout_agree_fraction: float = 0.5,
    max_attempts: int = 400,
    require_unique: bool = True,
) -> Optional[Instance]:
    """Generate one instance, or ``None`` if no acceptable one was found."""
    rng = random.Random(seed)
    domain = _domain(domain_size)
    all_points = [(a, b) for a in domain for b in domain]

    for attempt in range(max_attempts):
        true_template = TRUE_POOL[rng.randrange(len(TRUE_POOL))]
        surface_template = TRAP_POOL[rng.randrange(len(TRAP_POOL))]
        true_rule = true_template.compile()
        surface_rule = surface_template.compile()

        spec = discriminating_spec(true_rule, surface_rule)
        if spec is None:
            continue

        agreement = _agreement_points(true_rule, surface_rule, domain)
        disagreement = [p for p in all_points if p not in set(agreement)]
        if not agreement or not disagreement:
            continue

        # The training slice must be a small minority of the domain, otherwise
        # there is no "unseen region" for the trap to hide in.
        agreement_share = len(agreement) / len(all_points)
        if agreement_share > 0.7:
            continue

        training_points = rng.sample(agreement, min(train_size, len(agreement)))
        training = [
            {"a": a, "b": b, "y": true_rule(a, b, 0)} for a, b in training_points
        ]

        n_agree = max(1, int(round(heldout_size * heldout_agree_fraction)))
        n_disagree = max(1, heldout_size - n_agree)
        heldout_agree = rng.sample(agreement, min(n_agree, len(agreement)))
        heldout_disagree = rng.sample(disagreement, min(n_disagree, len(disagreement)))
        heldout_points = heldout_agree + heldout_disagree
        rng.shuffle(heldout_points)

        solutions = library_solutions(spec, training)
        well_posed = len(solutions) == 1
        if require_unique and not well_posed:
            continue

        return Instance(
            instance_id=f"A-{seed}-{attempt:03d}",
            seed=seed,
            domain=domain,
            spec_name=spec.name,
            true_rule_name=true_template.name,
            true_expr=true_template.expr(),
            surface_rule_name=surface_template.name,
            surface_expr=surface_template.expr(),
            training=training,
            heldout_inputs=[{"a": a, "b": b} for a, b in heldout_points],
            agreement_points=agreement,
            library_solutions=solutions,
            well_posed=well_posed,
        )

    return None


def generate_batch(
    count: int,
    seed_start: int = 0,
    **kwargs,
) -> List[Instance]:
    """Generate ``count`` instances, one per consecutive seed."""
    instances: List[Instance] = []
    seed = seed_start
    while len(instances) < count:
        instance = generate_instance(seed, **kwargs)
        if instance is not None:
            instances.append(instance)
        seed += 1
        if seed > seed_start + 10000:
            break
    return instances


def instance_to_dict(instance: Instance) -> Dict:
    data = asdict(instance)
    data["agreement_points"] = [list(point) for point in instance.agreement_points]
    return data


def instance_from_dict(data: Dict) -> Instance:
    data = dict(data)
    data["agreement_points"] = [tuple(point) for point in data.get("agreement_points", [])]
    return Instance(**data)
