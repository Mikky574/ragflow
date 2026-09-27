from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class VisualClass:
    name: str
    action: str
    prompts: tuple[str, ...]


def load_taxonomy(path: str | Path) -> dict[str, VisualClass]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    classes = raw.get("classes", {})
    if not classes:
        raise ValueError("taxonomy must define at least one class")

    result: dict[str, VisualClass] = {}
    for name, config in classes.items():
        prompts = tuple(config.get("prompts", ()))
        if not prompts:
            raise ValueError(f"class {name} has no prompts")
        action = config.get("action")
        if action not in {"index", "skip", "table"}:
            raise ValueError(f"class {name} has invalid action: {action!r}")
        result[name] = VisualClass(name=name, action=action, prompts=prompts)
    return result


def flatten_prompts(taxonomy: dict[str, VisualClass]) -> tuple[list[str], dict[str, str]]:
    prompts: list[str] = []
    prompt_to_class: dict[str, str] = {}
    for visual_class in taxonomy.values():
        for prompt in visual_class.prompts:
            prompts.append(prompt)
            prompt_to_class[prompt] = visual_class.name
    return prompts, prompt_to_class


def decide(scores: dict[str, float], taxonomy: dict[str, VisualClass], threshold: float) -> dict[str, Any]:
    if not scores:
        raise ValueError("scores must not be empty")
    visual_type, score = max(scores.items(), key=lambda item: item[1])
    visual_class = taxonomy[visual_type]
    decision = "review" if score < threshold else visual_class.action
    return {
        "visual_type": visual_type,
        "visual_score": round(float(score), 6),
        "index_action": decision,
    }
