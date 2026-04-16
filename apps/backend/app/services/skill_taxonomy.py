"""Shared skill grouping helpers for ATS-friendly resume output."""

from __future__ import annotations

from typing import Iterable

DATA_TOOL_HINTS = {
    "sql",
    "python",
    "numpy",
    "pandas",
    "data visualization",
    "tableau",
    "matplotlib",
    "excel",
    "statistics",
    "data modeling",
    "data transformation",
    "process analysis",
    "automation",
    "api integration",
    "lovable",
    "bolt.new",
    "notion",
    "asana",
}

PRODUCT_HINTS = {
    "agile scrum",
    "prd writing",
    "user story mapping",
    "lean canvas",
    "figma",
    "dogfooding",
    "a/b testing",
    "jira",
    "prototyping",
    "cross-functional collaboration",
    "product strategy",
    "customer discovery",
    "go-to-market",
    "solutioning",
}

PRODUCT_ORDER = [
    "agile scrum",
    "prd writing",
    "user story mapping",
    "lean canvas",
    "figma",
    "dogfooding",
    "a/b testing",
    "jira",
    "prototyping",
]

TOOL_ORDER = [
    "sql",
    "python",
    "numpy",
    "pandas",
    "data visualization",
    "tableau",
    "matplotlib",
    "excel",
    "lovable",
    "bolt.new",
    "notion",
    "asana",
    "automation",
    "api integration",
]


def _clean(skill: str) -> str:
    return " ".join(str(skill or "").strip().split())


def _normalized(skill: str) -> str:
    return _clean(skill).lower()


def is_data_tool_skill(skill: str) -> bool:
    normalized = _normalized(skill)
    if not normalized:
        return False
    if normalized in DATA_TOOL_HINTS:
        return True
    return any(hint in normalized for hint in ("sql", "python", "pandas", "numpy", "tableau", "excel", "data "))


def split_technical_skills(skills: Iterable[str]) -> tuple[list[str], list[str]]:
    product: list[str] = []
    tools: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        clean = _clean(skill)
        normalized = clean.lower()
        if not clean or normalized in seen:
            continue
        seen.add(normalized)
        if is_data_tool_skill(clean) and normalized not in PRODUCT_HINTS:
            tools.append(clean)
        else:
            product.append(clean)

    def _sort_key(skill: str, preferred: list[str]) -> tuple[int, str]:
        normalized = skill.lower()
        try:
            return (preferred.index(normalized), normalized)
        except ValueError:
            return (len(preferred), normalized)

    product.sort(key=lambda skill: _sort_key(skill, PRODUCT_ORDER))
    tools.sort(key=lambda skill: _sort_key(skill, TOOL_ORDER))

    return product, tools


def normalize_technical_skills(skills: Iterable[str]) -> list[str]:
    product, tools = split_technical_skills(skills)
    return [*product, *tools]
