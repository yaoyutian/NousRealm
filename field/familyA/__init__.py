"""Family A (格竹) — the trap task of NousRealm.

An instance hides two rules over the same inputs: a true rule and a simpler
surface rule that fits the training examples perfectly but is wrong outside the
slice they cover. A spec — a machine-checkable requirement — separates them.

See ``docs/phase1.md`` for the rationale and the field configuration.
"""

from .generator import Instance, generate_batch, generate_instance
from .rules import SPEC_BY_NAME, SPECS, RuleSpec
from .safe_eval import RuleError, compile_rule, try_compile
from .score import Response, Score, aggregate, score_instance

__all__ = [
    "Instance",
    "Response",
    "RuleError",
    "RuleSpec",
    "SPECS",
    "SPEC_BY_NAME",
    "Score",
    "aggregate",
    "compile_rule",
    "generate_batch",
    "generate_instance",
    "score_instance",
    "try_compile",
]
