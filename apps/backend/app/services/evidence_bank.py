"""Stored historical resume evidence bank for truthful tailoring."""

from __future__ import annotations

import json
import re
import copy
from functools import lru_cache
from typing import Any

from app.config import settings

EVIDENCE_BANK_PATH = settings.data_dir / "resume_evidence_bank.json"

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


@lru_cache(maxsize=1)
def load_evidence_bank() -> dict[str, Any]:
    if not EVIDENCE_BANK_PATH.exists():
        return {"resumes": []}
    try:
        return json.loads(EVIDENCE_BANK_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"resumes": []}


def invalidate_evidence_bank_cache() -> None:
    load_evidence_bank.cache_clear()


def _extract_current_resume_signals(resume_data: dict[str, Any] | None) -> tuple[set[str], set[str]]:
    companies: set[str] = set()
    projects: set[str] = set()
    if not resume_data:
        return companies, projects

    for entry in resume_data.get("workExperience", []):
        if isinstance(entry, dict):
            company = str(entry.get("company", "")).strip()
            if company:
                companies.add(_normalize(company))

    for entry in resume_data.get("personalProjects", []):
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            if name:
                projects.add(_normalize(name))

    return companies, projects


def _job_keyword_tokens(job_keywords: dict[str, Any] | None) -> set[str]:
    if not job_keywords:
        return set()
    values: list[str] = []
    for key in ("required_skills", "preferred_skills", "keywords", "key_responsibilities"):
        raw = job_keywords.get(key, [])
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if item)
    return _tokenize(" ".join(values))


def _score_text_against_keywords(text: str, keyword_tokens: set[str]) -> int:
    if not keyword_tokens:
        return 0
    return len(_tokenize(text) & keyword_tokens)


def _score_summary(text: str, keyword_tokens: set[str]) -> int:
    return _score_text_against_keywords(text, keyword_tokens)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _normalize(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item.strip())
    return result


def _is_near_duplicate(a: str, b: str) -> bool:
    a_tokens = _tokenize(a)
    b_tokens = _tokenize(b)
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return union > 0 and (overlap / union) >= 0.7


def _collect_experience_variants(company: str) -> list[str]:
    normalized_company = _normalize(company)
    variants: list[str] = []
    resumes = load_evidence_bank().get("resumes", [])
    for resume in resumes:
        if not isinstance(resume, dict):
            continue
        for entry in resume.get("experience", []):
            if not isinstance(entry, dict):
                continue
            if _normalize(str(entry.get("employer", ""))) == normalized_company:
                bullets = entry.get("bullets", [])
                if isinstance(bullets, list):
                    variants.extend(str(item).strip() for item in bullets if str(item).strip())
    return _dedupe_keep_order(variants)


def _collect_project_variants(project_name: str) -> list[str]:
    normalized_name = _normalize(project_name)
    variants: list[str] = []
    resumes = load_evidence_bank().get("resumes", [])
    for resume in resumes:
        if not isinstance(resume, dict):
            continue
        for entry in resume.get("projects", []):
            if not isinstance(entry, dict):
                continue
            if _normalize(str(entry.get("name", ""))) == normalized_name:
                bullets = entry.get("bullets", [])
                if isinstance(bullets, list):
                    variants.extend(str(item).strip() for item in bullets if str(item).strip())
    return _dedupe_keep_order(variants)


def _select_best_bullets(
    current_bullets: list[str],
    candidate_bullets: list[str],
    keyword_tokens: set[str],
) -> tuple[list[str], int]:
    target_count = max(1, len(current_bullets)) if current_bullets else min(max(len(candidate_bullets), 1), 4)
    all_candidates = _dedupe_keep_order([*current_bullets, *candidate_bullets])
    scored = sorted(
        all_candidates,
        key=lambda bullet: (
            _score_text_against_keywords(bullet, keyword_tokens),
            len(_tokenize(bullet)),
        ),
        reverse=True,
    )

    selected: list[str] = []
    for bullet in scored:
        if any(_is_near_duplicate(bullet, existing) for existing in selected):
            continue
        selected.append(bullet)
        if len(selected) >= target_count:
            break

    if len(selected) < target_count:
        for bullet in scored:
            if bullet in selected:
                continue
            selected.append(bullet)
            if len(selected) >= target_count:
                break
    modifications = 0
    for idx, bullet in enumerate(selected):
        if idx >= len(current_bullets) or _normalize(current_bullets[idx]) != _normalize(bullet):
            modifications += 1
    return selected, modifications


def apply_evidence_bank_variants(
    improved_data: dict[str, Any],
    original_resume_data: dict[str, Any] | None,
    job_keywords: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Deterministically strengthen summary and bullets using stored historical variants."""
    if not improved_data:
        return improved_data, []

    keyword_tokens = _job_keyword_tokens(job_keywords)
    result = copy.deepcopy(improved_data)
    warnings: list[str] = []

    # Summary selection
    bank = load_evidence_bank().get("resumes", [])
    current_summary = str(result.get("summary", "")).strip()
    current_summary_score = _score_summary(current_summary, keyword_tokens)
    best_summary = current_summary
    best_summary_score = current_summary_score
    for resume in bank:
        if not isinstance(resume, dict):
            continue
        summary = str(resume.get("summary", "")).strip()
        if not summary:
            continue
        score = _score_summary(summary, keyword_tokens)
        if score > best_summary_score:
            best_summary = summary
            best_summary_score = score
    if best_summary and best_summary != current_summary and best_summary_score >= current_summary_score:
        result["summary"] = best_summary
        warnings.append("Used a stronger historical summary variant from your stored resume bank.")

    # Experience bullets
    total_modifications = 0
    for entry in result.get("workExperience", []):
        if not isinstance(entry, dict):
            continue
        company = str(entry.get("company", "")).strip()
        if not company:
            continue
        current_bullets = [
            str(item).strip()
            for item in entry.get("description", [])
            if str(item).strip()
        ]
        candidate_bullets = _collect_experience_variants(company)
        if not candidate_bullets:
            continue
        selected, modifications = _select_best_bullets(current_bullets, candidate_bullets, keyword_tokens)
        if modifications > 0:
            entry["description"] = selected
            total_modifications += modifications

    # Project bullets
    for entry in result.get("personalProjects", []):
        if not isinstance(entry, dict):
            continue
        project_name = str(entry.get("name", "")).strip()
        if not project_name:
            continue
        current_bullets = [
            str(item).strip()
            for item in entry.get("description", [])
            if str(item).strip()
        ]
        candidate_bullets = _collect_project_variants(project_name)
        if not candidate_bullets:
            continue
        selected, modifications = _select_best_bullets(current_bullets, candidate_bullets, keyword_tokens)
        if modifications > 0:
            entry["description"] = selected
            total_modifications += modifications

    if total_modifications > 0:
        warnings.append(
            f"Applied {total_modifications} stronger bullet variant(s) from your stored historical resumes."
        )

    # Preserve original structure counts if a master exists
    if original_resume_data:
        for idx, original_entry in enumerate(original_resume_data.get("workExperience", [])):
            if idx < len(result.get("workExperience", [])) and isinstance(original_entry, dict):
                original_count = len(original_entry.get("description", []) or [])
                if original_count > 0:
                    result["workExperience"][idx]["description"] = result["workExperience"][idx]["description"][:original_count]
        for idx, original_entry in enumerate(original_resume_data.get("personalProjects", [])):
            if idx < len(result.get("personalProjects", [])) and isinstance(original_entry, dict):
                original_count = len(original_entry.get("description", []) or [])
                if original_count > 0:
                    result["personalProjects"][idx]["description"] = result["personalProjects"][idx]["description"][:original_count]

    return result, warnings


def build_evidence_bank_context(
    current_resume_data: dict[str, Any] | None,
    job_keywords: dict[str, Any] | None,
) -> str:
    """Select the most relevant stored resume evidence for the current tailoring task."""
    bank = load_evidence_bank()
    resumes = bank.get("resumes", [])
    if not isinstance(resumes, list) or not resumes:
        return "No historical resume evidence available."

    current_companies, current_projects = _extract_current_resume_signals(current_resume_data)
    keyword_tokens = _job_keyword_tokens(job_keywords)

    summary_candidates: list[tuple[int, str, str]] = []
    experience_matches: list[dict[str, Any]] = []
    project_candidates: list[tuple[int, dict[str, Any]]] = []

    for resume in resumes:
        if not isinstance(resume, dict):
            continue
        title = str(resume.get("source_title", "")).strip()
        summary = str(resume.get("summary", "")).strip()
        if summary:
            summary_candidates.append(
                (_score_text_against_keywords(summary, keyword_tokens), title, summary)
            )

        for entry in resume.get("experience", []):
            if not isinstance(entry, dict):
                continue
            employer = _normalize(str(entry.get("employer", "")))
            if employer and employer in current_companies:
                experience_matches.append(
                    {
                        "source_title": title,
                        "employer": entry.get("employer", ""),
                        "role": entry.get("role", ""),
                        "bullets": entry.get("bullets", [])[:6],
                    }
                )

        for entry in resume.get("projects", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            score = _score_text_against_keywords(
                " ".join([name, " ".join(entry.get("bullets", []))]),
                keyword_tokens,
            )
            normalized_name = _normalize(name)
            if normalized_name and normalized_name in current_projects:
                score += 3
            project_candidates.append(
                (
                    score,
                    {
                        "source_title": title,
                        "name": name,
                        "bullets": entry.get("bullets", [])[:4],
                    },
                )
            )

    summary_candidates.sort(key=lambda item: item[0], reverse=True)
    project_candidates.sort(key=lambda item: item[0], reverse=True)

    context = {
        "summary_variants": [
            {"source_title": title, "summary": summary}
            for _, title, summary in summary_candidates[:3]
        ],
        "experience_variants": experience_matches[:6],
        "project_variants": [entry for _, entry in project_candidates[:6]],
    }

    if not context["summary_variants"] and not context["experience_variants"] and not context["project_variants"]:
        return "No historical resume evidence available."

    return json.dumps(context, ensure_ascii=False)
