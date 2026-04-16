"""Portfolio evidence reader for public portfolio sources such as Notion."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.llm import complete_json

logger = logging.getLogger(__name__)

_SUPPORTED_HOST_SUFFIXES = (
    ".notion.site",
    ".notion.so",
)
_SUPPORTED_HOSTS = {
    "notion.site",
    "www.notion.so",
    "notion.so",
}

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")

PORTFOLIO_EVIDENCE_PROMPT = """You are extracting grounded portfolio evidence for a resume tailoring assistant.

SOURCE URL:
{portfolio_url}

SOURCE TITLE:
{portfolio_title}

PORTFOLIO TEXT:
{portfolio_text}

TASK:
Extract only evidence that appears in the source text. Focus on projects, product work, tools, outcomes, user problems, collaborators, and measurable impact.

OUTPUT JSON ONLY:
{{
  "summary": "1-2 sentence summary of the portfolio focus",
  "transferable_skills": ["skill 1", "skill 2"],
  "projects": [
    {{
      "name": "project name",
      "tools": ["tool 1", "tool 2"],
      "outcomes": ["outcome or impact phrase"],
      "evidence": ["short factual note from the portfolio"],
      "role_hint": "optional role phrasing already supported by the portfolio"
    }}
  ]
}}

RULES:
- Do not invent metrics, titles, tools, or outcomes.
- If the portfolio text is vague, stay vague.
- Keep evidence short and factual.
- Return at most 8 transferable skills.
- Return at most 8 projects.
- If no reliable evidence exists, return empty arrays and a short summary.
"""


def _strip_html(html: str) -> str:
    cleaned = _SCRIPT_STYLE_RE.sub(" ", html)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = cleaned.replace("\r", "\n")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _extract_title(html: str, fallback_url: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = _strip_html(match.group(1)).strip()
        if title:
            return title[:200]
    return fallback_url


def _validate_portfolio_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        raise ValueError("Portfolio URL is required.")

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Portfolio URL must start with http:// or https://")

    host = (parsed.netloc or "").lower()
    if host not in _SUPPORTED_HOSTS and not host.endswith(_SUPPORTED_HOST_SUFFIXES):
        raise ValueError("Portfolio reader currently supports public Notion URLs only.")

    return normalized


def _fetch_public_page(url: str) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "ResumeMatcher/1.0 (+portfolio-reader)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - user-provided URL validated to supported hosts
        raw_bytes = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw_bytes.decode(charset, errors="replace")
    title = _extract_title(html, url)
    text = _strip_html(html)
    return title, text[:24000]


async def _summarize_portfolio_text(
    *,
    portfolio_title: str,
    portfolio_text: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    prompt = PORTFOLIO_EVIDENCE_PROMPT.format(
        portfolio_url=source_url or "(manual paste)",
        portfolio_title=portfolio_title,
        portfolio_text=portfolio_text,
    )

    result = await complete_json(
        prompt=prompt,
        system_prompt="You extract only grounded portfolio evidence. Output valid JSON only.",
        max_tokens=2200,
    )

    projects = result.get("projects")
    if not isinstance(projects, list):
        projects = []

    transferable_skills = result.get("transferable_skills")
    if not isinstance(transferable_skills, list):
        transferable_skills = []

    evidence = {
        "source_type": "notion" if source_url else "manual",
        "source_url": source_url,
        "title": portfolio_title,
        "summary": str(result.get("summary", "")).strip(),
        "transferable_skills": [
            str(skill).strip()
            for skill in transferable_skills
            if isinstance(skill, str) and str(skill).strip()
        ][:8],
        "projects": [],
        "raw_excerpt": portfolio_text[:4000],
    }

    for project in projects[:8]:
        if not isinstance(project, dict):
            continue
        evidence["projects"].append(
            {
                "name": str(project.get("name", "")).strip(),
                "tools": [
                    str(item).strip()
                    for item in project.get("tools", [])
                    if isinstance(item, str) and str(item).strip()
                ][:8],
                "outcomes": [
                    str(item).strip()
                    for item in project.get("outcomes", [])
                    if isinstance(item, str) and str(item).strip()
                ][:6],
                "evidence": [
                    str(item).strip()
                    for item in project.get("evidence", [])
                    if isinstance(item, str) and str(item).strip()
                ][:6],
                "role_hint": str(project.get("role_hint", "")).strip(),
            }
        )

    logger.info(
        "Loaded portfolio evidence from %s with %d project(s)",
        source_url or "manual text",
        len(evidence["projects"]),
    )
    return evidence


async def load_portfolio_evidence(
    portfolio_url: str | None = None,
    portfolio_text: str | None = None,
) -> dict[str, Any]:
    """Fetch and summarize portfolio evidence from URL or pasted text."""
    if portfolio_text and portfolio_text.strip():
        cleaned = portfolio_text.strip()[:24000]
        return await _summarize_portfolio_text(
            portfolio_title="Portfolio Notes",
            portfolio_text=cleaned,
            source_url=portfolio_url.strip() if portfolio_url else None,
        )

    if not portfolio_url:
        raise ValueError("Portfolio URL or portfolio text is required.")

    validated_url = _validate_portfolio_url(portfolio_url)
    portfolio_title, page_text = await asyncio.to_thread(_fetch_public_page, validated_url)

    if not page_text or len(page_text.split()) < 40:
        raise ValueError(
            "This Notion page was not readable through direct fetch. Paste portfolio text below for now."
        )

    return await _summarize_portfolio_text(
        portfolio_title=portfolio_title,
        portfolio_text=page_text,
        source_url=validated_url,
    )


def format_portfolio_context(portfolio_evidence: dict[str, Any] | None) -> str:
    """Format portfolio evidence for prompts."""
    if not portfolio_evidence:
        return "No portfolio evidence provided."

    compact = {
        "summary": portfolio_evidence.get("summary", ""),
        "transferable_skills": portfolio_evidence.get("transferable_skills", []),
        "projects": portfolio_evidence.get("projects", []),
        "source_url": portfolio_evidence.get("source_url", ""),
    }
    return json.dumps(compact, ensure_ascii=False)
