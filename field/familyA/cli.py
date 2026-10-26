"""Command line interface for Family A.

    python -m field.familyA batch      --count 50 --out runs/familyA
    python -m field.familyA selfcheck  --count 200
    python -m field.familyA score      --instances runs/familyA --responses r.json
    python -m field.familyA human      --instances runs/familyA --out human.md
    python -m field.familyA selftest

Instances are written in two directories: ``instances/`` (safe to hand to a
model) and ``keys/`` (answers, never handed to a model).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Dict, List

from .generator import generate_batch, instance_to_dict
from .rules import SPEC_BY_NAME
from .safe_eval import RuleError, compile_rule
from .score import aggregate, load_responses, score_instance


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def cmd_batch(args: argparse.Namespace) -> int:
    instances = generate_batch(
        count=args.count,
        seed_start=args.seed_start,
        domain_size=args.domain_size,
        train_size=args.train_size,
        heldout_size=args.heldout_size,
        require_unique=not args.allow_ambiguous,
    )
    if not instances:
        print("no instances generated", file=sys.stderr)
        return 1
    for instance in instances:
        _write_json(
            os.path.join(args.out, "instances", f"{instance.instance_id}.json"),
            instance.visible(),
        )
        _write_json(
            os.path.join(args.out, "keys", f"{instance.instance_id}.json"),
            instance.key(),
        )
    print(f"wrote {len(instances)} instances to {args.out}")
    return 0


def cmd_selfcheck(args: argparse.Namespace) -> int:
    instances = generate_batch(
        count=args.count,
        seed_start=args.seed_start,
        domain_size=args.domain_size,
        train_size=args.train_size,
        heldout_size=args.heldout_size,
        require_unique=not args.allow_ambiguous,
    )
    if not instances:
        print("no instances generated", file=sys.stderr)
        return 1

    spec_counts: Dict[str, int] = {}
    shares: List[float] = []
    solution_counts: List[int] = []
    surface_accs: List[float] = []
    for instance in instances:
        spec_counts[instance.spec_name] = spec_counts.get(instance.spec_name, 0) + 1
        total = len(instance.domain) ** 2
        shares.append(len(instance.agreement_points) / total)
        solution_counts.append(len(instance.library_solutions))
        key = instance.key()
        if key["surface_acc"] is not None:
            surface_accs.append(key["surface_acc"])

    print(f"instances            : {len(instances)}")
    print(f"well-posed (1 soln)  : {sum(1 for c in solution_counts if c == 1)}/{len(instances)}")
    print(f"agreement share      : min {min(shares):.2f} mean {statistics.mean(shares):.2f} max {max(shares):.2f}")
    if surface_accs:
        print(f"surface rule acc     : min {min(surface_accs):.2f} mean {statistics.mean(surface_accs):.2f} max {max(surface_accs):.2f}")
    print("spec distribution    :")
    for name, count in sorted(spec_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<18} {count:>4}  ({100 * count / len(instances):.1f}%)")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    responses = load_responses(args.responses)
    instances_dir = os.path.join(args.instances, "instances")
    keys_dir = os.path.join(args.instances, "keys")
    if not os.path.isdir(instances_dir):
        print(f"no instances at {instances_dir}", file=sys.stderr)
        return 1

    cache: Dict[str, tuple] = {}
    scores = []
    unmatched = []
    for response in responses:
        if response.instance_id not in cache:
            path = os.path.join(instances_dir, f"{response.instance_id}.json")
            if not os.path.exists(path):
                cache[response.instance_id] = None
            else:
                with open(path, "r", encoding="utf-8") as handle:
                    visible = json.load(handle)
                with open(os.path.join(keys_dir, f"{response.instance_id}.json"), "r", encoding="utf-8") as handle:
                    key = json.load(handle)
                domain = visible["domain"]
                cache[response.instance_id] = (
                    visible,
                    key,
                    SPEC_BY_NAME[visible["spec"]["name"]],
                    [(a, b) for a in domain for b in domain],
                )
        entry = cache[response.instance_id]
        if entry is None:
            unmatched.append(response.instance_id)
            continue
        visible, key, spec, domain_points = entry
        scores.append(score_instance(visible, key, response, spec, domain_points))

    if not scores:
        print("no scored instances — check that response instance_ids match", file=sys.stderr)
        return 1

    summary = aggregate(scores)
    _write_json(args.out, {"summary": summary, "scores": [s.to_dict() for s in scores]})
    print(json.dumps(summary, indent=2))
    if unmatched:
        print(f"warning: {len(unmatched)} responses had no matching instance", file=sys.stderr)
    return 0


def cmd_human(args: argparse.Namespace) -> int:
    """Emit a human ceiling-check sheet: the task, then the answers separately."""
    instances_dir = os.path.join(args.instances, "instances")
    keys_dir = os.path.join(args.instances, "keys")
    lines = ["# Family A — 人类天花板检查 / human ceiling check", ""]
    answers = ["# Answers", ""]
    for filename in sorted(os.listdir(instances_dir)):
        if not filename.endswith(".json"):
            continue
        instance_id = filename[: -len(".json")]
        with open(os.path.join(instances_dir, filename), "r", encoding="utf-8") as handle:
            visible = json.load(handle)
        with open(os.path.join(keys_dir, filename), "r", encoding="utf-8") as handle:
            key = json.load(handle)

        lines.append(f"## {instance_id}")
        lines.append("")
        lines.append(f"- Spec: **{visible['spec']['text']}**")
        lines.append(f"- 输入范围 a, b ∈ {visible['domain']}")
        lines.append("")
        lines.append("| a | b | y |")
        lines.append("|---|---|---|")
        for example in visible["training"]:
            lines.append(f"| {example['a']} | {example['b']} | {example['y']} |")
        lines.append("")
        lines.append("Held-out inputs (predict y for each):")
        lines.append("")
        lines.append("```")
        for point in visible["heldout_inputs"]:
            lines.append(f"({point['a']}, {point['b']})")
        lines.append("```")
        lines.append("")
        answers.append(f"## {instance_id}")
        answers.append("")
        answers.append(f"- true rule: `{key['true_expr']}`")
        answers.append(f"- surface rule: `{key['surface_expr']}`")
        answers.append(f"- spec: {visible['spec']['name']}")
        answers.append("")

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    answer_path = args.out.replace(".md", "-answers.md")
    with open(answer_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(answers))
    print(f"wrote {args.out} and {answer_path}")
    return 0


SELFTEST_ACCEPT = [
    "(a + b) % 2",
    "abs(a - b) % 3",
    "a % 2 if b > 3 else b % 2",
    "max(a, b)",
    "not (a == b)",
    "(a ** 2 + b ** 2) % 3",
    "int(a / 3) + b",
]

SELFTEST_REJECT = [
    "__import__('os').system('echo hi')",
    "open('/etc/passwd').read()",
    "().__class__",
    "(lambda: 1)()",
    "[x for x in range(10)]",
    "a.__dict__",
    "a[0]",
    "2 ** 100",
    "a % 0",
    "globals()",
    "eval('1')",
    "a; b",
]


def cmd_selftest(args: argparse.Namespace) -> int:
    failures = []
    for expr in SELFTEST_ACCEPT:
        try:
            rule = compile_rule(expr)
            rule(3, 4, 0)
        except RuleError as exc:
            failures.append(f"should ACCEPT but rejected: {expr!r} ({exc})")
    for expr in SELFTEST_REJECT:
        try:
            rule = compile_rule(expr)
            rule(3, 4, 0)
        except RuleError:
            continue
        failures.append(f"should REJECT but accepted: {expr!r}")
    if failures:
        print("SANDBOX SELFTEST FAILED", file=sys.stderr)
        for failure in failures:
            print("  " + failure, file=sys.stderr)
        return 1
    print(f"sandbox selftest passed ({len(SELFTEST_ACCEPT)} accepted, {len(SELFTEST_REJECT)} rejected)")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="field.familyA", description="Family A task generator")
    sub = parser.add_subparsers(dest="command", required=True)

    batch = sub.add_parser("batch", help="generate instances")
    batch.add_argument("--count", type=int, default=50)
    batch.add_argument("--seed-start", type=int, default=0)
    batch.add_argument("--out", default="runs/familyA")
    batch.add_argument("--domain-size", type=int, default=10)
    batch.add_argument("--train-size", type=int, default=12)
    batch.add_argument("--heldout-size", type=int, default=20)
    batch.add_argument("--allow-ambiguous", action="store_true")
    batch.set_defaults(func=cmd_batch)

    selfcheck = sub.add_parser("selfcheck", help="generation statistics over many seeds")
    selfcheck.add_argument("--count", type=int, default=200)
    selfcheck.add_argument("--seed-start", type=int, default=0)
    selfcheck.add_argument("--domain-size", type=int, default=10)
    selfcheck.add_argument("--train-size", type=int, default=12)
    selfcheck.add_argument("--heldout-size", type=int, default=20)
    selfcheck.add_argument("--allow-ambiguous", action="store_true")
    selfcheck.set_defaults(func=cmd_selfcheck)

    score = sub.add_parser("score", help="score responses offline")
    score.add_argument("--instances", required=True)
    score.add_argument("--responses", required=True)
    score.add_argument("--out", default="runs/familyA/scores.json")
    score.set_defaults(func=cmd_score)

    human = sub.add_parser("human", help="emit a human ceiling-check sheet")
    human.add_argument("--instances", required=True)
    human.add_argument("--out", default="runs/familyA/human.md")
    human.set_defaults(func=cmd_human)

    selftest = sub.add_parser("selftest", help="check the expression sandbox")
    selftest.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
