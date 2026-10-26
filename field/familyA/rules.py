"""Rule pools and specs for Family A (格竹).

A task instance hides two rules over the same input domain:

* the **true rule** ``R`` — what actually generated the labels;
* the **surface rule** ``S`` — a simpler rule that happens to fit the training
  examples perfectly, and is wrong outside the slice the training examples cover.

The two are made distinguishable only by a **spec**: a machine-checkable
requirement that ``R`` satisfies and ``S`` violates. Without it, the surface
rule is the Occam-optimal answer and escaping the trap would be irrational.

The rule language is the sandboxed expression language of :mod:`safe_eval`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

from .safe_eval import RuleError, compile_rule

Rule = Callable[[int, int, int], object]


@dataclass(frozen=True)
class RuleSpec:
    """A machine-checkable requirement on a rule."""

    name: str
    text_en: str
    text_zh: str
    check: Callable[[Rule], bool]


def _spec_symmetric(rule: Rule) -> bool:
    for a in range(10):
        for b in range(10):
            try:
                if rule(a, b, 0) != rule(b, a, 0):
                    return False
            except RuleError:
                return False
    return True


def _spec_depends_on_both(rule: Rule) -> bool:
    varies_in_b = False
    varies_in_a = False
    for a in range(10):
        try:
            values = {rule(a, b, 0) for b in range(10)}
        except RuleError:
            return False
        if len(values) > 1:
            varies_in_b = True
            break
    for b in range(10):
        try:
            values = {rule(a, b, 0) for a in range(10)}
        except RuleError:
            return False
        if len(values) > 1:
            varies_in_a = True
            break
    return varies_in_b and varies_in_a


def _spec_zero_at_origin(rule: Rule) -> bool:
    try:
        return rule(0, 0, 0) == 0
    except RuleError:
        return False


def _spec_nonnegative(rule: Rule) -> bool:
    for a in range(10):
        for b in range(10):
            try:
                if rule(a, b, 0) < 0:
                    return False
            except RuleError:
                return False
    return True


def _spec_value_lt_3(rule: Rule) -> bool:
    for a in range(10):
        for b in range(10):
            try:
                if not 0 <= rule(a, b, 0) < 3:
                    return False
            except RuleError:
                return False
    return True


SPECS: Tuple[RuleSpec, ...] = (
    RuleSpec(
        name="symmetric",
        text_en="The rule must satisfy f(a, b) == f(b, a) for every input.",
        text_zh="规则必须满足 f(a, b) == f(b, a) 对所有输入成立。",
        check=_spec_symmetric,
    ),
    RuleSpec(
        name="depends_on_both",
        text_en=(
            "The rule must genuinely depend on both inputs: fixing one input must "
            "leave the output variable, and vice versa."
        ),
        text_zh="规则必须真正依赖两个输入：固定任一输入，输出都必须随之变化。",
        check=_spec_depends_on_both,
    ),
    RuleSpec(
        name="zero_at_origin",
        text_en="The rule must satisfy f(0, 0) == 0.",
        text_zh="规则必须满足 f(0, 0) == 0。",
        check=_spec_zero_at_origin,
    ),
    RuleSpec(
        name="value_lt_3",
        text_en="The rule must always return a value in [0, 3).",
        text_zh="规则的返回值必须始终落在 [0, 3) 区间内。",
        check=_spec_value_lt_3,
    ),
    RuleSpec(
        name="nonnegative",
        text_en="The rule must never return a negative value.",
        text_zh="规则的返回值不得为负。",
        check=_spec_nonnegative,
    ),
)

SPEC_BY_NAME: Dict[str, RuleSpec] = {spec.name: spec for spec in SPECS}

# Specs are tried in this order. Stronger, more specific specs come first
# because they discriminate more sharply between the true and surface rules.
SPEC_ORDER: Tuple[str, ...] = ("symmetric", "depends_on_both", "value_lt_3", "zero_at_origin", "nonnegative")


@dataclass(frozen=True)
class RuleTemplate:
    """A rule written with ``{a}`` / ``{b}`` placeholders."""

    name: str
    template: str

    def expr(self) -> str:
        return self.template.format(a="a", b="b")

    def compile(self) -> Rule:
        return compile_rule(self.expr())


# Richer rules: these may serve as the true rule.
TRUE_POOL: Tuple[RuleTemplate, ...] = (
    RuleTemplate("par_sum", "({a} + {b}) % 2"),
    RuleTemplate("par_prod", "({a} * {b}) % 2"),
    RuleTemplate("mod3_lin", "({a} + 2 * {b}) % 3"),
    RuleTemplate("mod4_sum", "({a} + {b}) % 4"),
    RuleTemplate("mod5_sq", "({a} ** 2 + {b}) % 5"),
    RuleTemplate("mod3_quad", "({a} ** 2 + {b} ** 2) % 3"),
    RuleTemplate("absdiff3", "abs({a} - {b}) % 3"),
    RuleTemplate("half_par", "(({a} + {b}) // 2) % 2"),
)

# Simpler, more tempting rules: these may serve as the surface (trap) rule.
TRAP_POOL: Tuple[RuleTemplate, ...] = (
    RuleTemplate("a_mod2", "{a} % 2"),
    RuleTemplate("b_mod2", "{b} % 2"),
    RuleTemplate("a_mod3", "{a} % 3"),
    RuleTemplate("b_mod3", "{b} % 3"),
    RuleTemplate("a_mod4", "{a} % 4"),
    RuleTemplate("b_mod4", "{b} % 4"),
    RuleTemplate("a_mod5", "{a} % 5"),
    RuleTemplate("const0", "0"),
)

# Used only by the solvability check, never handed to the model.
FULL_POOL: Tuple[RuleTemplate, ...] = TRUE_POOL + TRAP_POOL


def fits_examples(rule: Rule, examples: Sequence[Dict[str, int]]) -> bool:
    """True when ``rule`` reproduces the label of every example."""
    for example in examples:
        try:
            if rule(example["a"], example["b"], 0) != example["y"]:
                return False
        except RuleError:
            return False
    return True


def discriminating_spec(
    true_rule: Rule,
    surface_rule: Rule,
    order: Sequence[str] = SPEC_ORDER,
) -> RuleSpec | None:
    """The first spec that the true rule satisfies and the surface rule violates."""
    for name in order:
        spec = SPEC_BY_NAME[name]
        if spec.check(true_rule) and not spec.check(surface_rule):
            return spec
    return None


def library_solutions(
    spec: RuleSpec,
    examples: Sequence[Dict[str, int]],
    pool: Sequence[RuleTemplate] = FULL_POOL,
) -> List[str]:
    """Names of library rules that fit the examples *and* satisfy the spec.

    A well-posed instance has exactly one. This is a proxy for solvability: the
    model is free to invent rules outside the library, so uniqueness here does
    not guarantee a unique answer in the model's eyes — only that the library
    pins it down.
    """
    solutions: List[str] = []
    for template in pool:
        rule = template.compile()
        if fits_examples(rule, examples) and spec.check(rule):
            solutions.append(template.name)
    return solutions
