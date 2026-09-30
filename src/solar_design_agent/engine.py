"""Domain-neutral optimization primitives for engineering design problems."""

from dataclasses import dataclass
from typing import Generic, Iterable, Mapping, Protocol, TypeVar

DesignT = TypeVar("DesignT")


class DesignProblem(Protocol[DesignT]):
    """Contract implemented by a domain-specific engineering problem."""

    def candidate_designs(self) -> Iterable[DesignT]:
        ...

    def evaluate(self, design: DesignT) -> Mapping[str, float]:
        ...

    def is_feasible(self, design: DesignT, metrics: Mapping[str, float]) -> bool:
        ...

    def score(self, design: DesignT, metrics: Mapping[str, float]) -> float:
        ...


@dataclass(frozen=True)
class DesignEvaluation(Generic[DesignT]):
    design: DesignT
    metrics: dict[str, float]
    feasible: bool
    score: float


def optimize_problem(problem: DesignProblem[DesignT]) -> dict[str, object]:
    """Evaluate a finite design space and return the best feasible design."""
    evaluations: list[DesignEvaluation[DesignT]] = []
    for design in problem.candidate_designs():
        metrics = dict(problem.evaluate(design))
        feasible = problem.is_feasible(design, metrics)
        evaluations.append(DesignEvaluation(design, metrics, feasible, problem.score(design, metrics)))
    feasible = [evaluation for evaluation in evaluations if evaluation.feasible]
    if not feasible:
        raise ValueError("no feasible design was found")
    best = max(feasible, key=lambda evaluation: evaluation.score)
    return {"best": best, "evaluations": evaluations, "feasible_count": len(feasible)}
