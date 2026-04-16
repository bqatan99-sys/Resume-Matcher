"""LaTeX export helpers using the April 14 one-page resume layout."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from app.errors import PDFRenderError
from app.services.skill_taxonomy import split_technical_skills


MASTER_LATEX_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4] / "latex" / "basher_april14_master.tex"
)
REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_TECTONIC_PATH = REPO_ROOT / "tectonic"
LATEX_COMPILERS = ("tectonic", "latexmk", "xelatex", "pdflatex", "lualatex")
DEFAULT_MASTER_TEMPLATE = r"""\documentclass[10pt]{article}

\usepackage[letterpaper,margin=0.44in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{times}
\usepackage[hidelinks]{hyperref}
\urlstyle{same}
\usepackage{enumitem}
\usepackage{tabularx}
\usepackage{array}
\usepackage{titlesec}
\usepackage{xcolor}
\usepackage{ragged2e}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\setlist[itemize]{leftmargin=1.25em, labelsep=0.45em, labelwidth=0.55em, itemindent=0pt, listparindent=0pt, itemsep=0.1em, topsep=0.15em, parsep=0em, partopsep=0em}

\titleformat{\section}
  {\normalfont\bfseries\normalsize}
  {}
  {0pt}
  {}
  [\titlerule]
\titlespacing*{\section}{0pt}{0.42em}{0.34em}

\newcommand{\ResumeHeader}[2]{
  \begin{center}
    {\Large\bfseries #1}\par
    \vspace{0.12em}
    {\footnotesize #2}
  \end{center}
}

\newcommand{\Entry}[4]{
  \begin{tabularx}{\textwidth}{@{}X>{\raggedleft\arraybackslash}p{2.85cm}@{}}
    \textbf{#1} #2 & {\small\bfseries #3} \\
  \end{tabularx}
  {\itshape #4}\par
  \vspace{0.16em}
}

\newcommand{\ProjectLine}[2]{
  \textbf{#1}: #2\par
  \vspace{0.16em}
}

\newcommand{\SkillLine}[2]{
  \textbf{#1} #2\par
}

\begin{document}

@@HEADER_BLOCK@@
@@SUMMARY_BLOCK@@
@@EDUCATION_BLOCK@@
@@EXPERIENCE_BLOCK@@
@@PROJECTS_BLOCK@@
@@SKILLS_BLOCK@@

\end{document}
"""

def has_master_latex_template() -> bool:
    return MASTER_LATEX_TEMPLATE_PATH.exists()


def _load_master_template() -> str:
    if MASTER_LATEX_TEMPLATE_PATH.exists():
        return MASTER_LATEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    return DEFAULT_MASTER_TEMPLATE


def _find_compiler() -> str | None:
    for compiler in LATEX_COMPILERS:
        executable = shutil.which(compiler)
        if executable:
            return executable
        if compiler == "tectonic" and LOCAL_TECTONIC_PATH.exists():
            return str(LOCAL_TECTONIC_PATH)
    return None


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _shorten_date_range(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    replacements = {
        "January": "Jan",
        "February": "Feb",
        "March": "Mar",
        "April": "Apr",
        "June": "Jun",
        "July": "Jul",
        "August": "Aug",
        "September": "Sep",
        "October": "Oct",
        "November": "Nov",
        "December": "Dec",
    }
    for full, short in replacements.items():
        text = re.sub(rf"\b{full}\b", short, text)
    text = re.sub(r"\s*[–—-]\s*", " - ", text)
    return text


def _latex_date_cell(value: Any) -> str:
    text = _shorten_date_range(value)
    if not text:
        return ""
    # Keep the range on one visual line and preserve the separator.
    return r"\mbox{%s}" % _escape_latex(text).replace(" ", "~")


def _normalize_url(value: str, kind: str = "web") -> str:
    text = value.strip()
    if not text:
        return ""
    lower = text.lower()
    if kind == "email":
        return text if lower.startswith("mailto:") else f"mailto:{text}"
    if kind == "phone":
        return text if lower.startswith("tel:") else f"tel:{text}"
    return text if lower.startswith(("http://", "https://")) else f"https://{text}"


def _contact_segments(personal_info: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    location = _clean_text(personal_info.get("location"))
    email = _clean_text(personal_info.get("email"))
    phone = _clean_text(personal_info.get("phone"))
    linkedin = _clean_text(personal_info.get("linkedin"))
    website = _clean_text(personal_info.get("website"))
    github = _clean_text(personal_info.get("github"))

    if location:
        parts.append(_escape_latex(location))
    if email:
        parts.append(r"\href{%s}{%s}" % (_normalize_url(email, "email"), _escape_latex(email)))
    if phone:
        parts.append(r"\href{%s}{%s}" % (_normalize_url(phone, "phone"), _escape_latex(phone)))
    if linkedin:
        parts.append(r"\href{%s}{LinkedIn}" % _normalize_url(linkedin))
    if website:
        parts.append(r"\href{%s}{Portfolio}" % _normalize_url(website))
    if github:
        parts.append(r"\href{%s}{GitHub}" % _normalize_url(github))
    return parts


def _latex_bullet_list(items: list[str]) -> list[str]:
    lines = [_clean_text(item) for item in items if _clean_text(item)]
    if not lines:
        return []
    block = [r"\begin{itemize}"]
    for item in lines:
        clean_item = item[:-1] if item.endswith(".") else item
        block.append(r"  \item %s" % _escape_latex(clean_item))
    block.append(r"\end{itemize}")
    return block


def _split_technical_skills(skills: list[str]) -> tuple[list[str], list[str]]:
    return split_technical_skills(_clean_text(skill) for skill in skills)


def _project_line(project: dict[str, Any]) -> str | None:
    name = _clean_text(project.get("name"))
    description_parts = [
        _escape_latex(_clean_text(item))
        for item in (project.get("description") or [])
        if _clean_text(item)
    ]
    if not name and not description_parts:
        return None

    github = _clean_text(project.get("github"))
    website = _clean_text(project.get("website"))
    primary_url = _normalize_url(website) if website else (_normalize_url(github) if github else "")
    display_name = (
        r"\href{%s}{%s}" % (primary_url, _escape_latex(name))
        if name and primary_url
        else _escape_latex(name)
    )
    links: list[str] = []
    if github and _normalize_url(github) != primary_url:
        links.append(r"\href{%s}{GitHub}" % _normalize_url(github))
    if website and _normalize_url(website) != primary_url:
        links.append(r"\href{%s}{Website}" % _normalize_url(website))
    if links:
        description_parts.append("(" + " | ".join(links) + ")")

    return r"\ProjectLine{%s}{%s}" % (
        display_name,
        " ".join(description_parts),
    )


def _render_header_block(personal_info: dict[str, Any]) -> str:
    contact_parts = _contact_segments(personal_info)
    name = _escape_latex(_clean_text(personal_info.get("name")))
    return "\n".join(
        [
            r"\ResumeHeader",
            f"  {{{name}}}",
            "  {" + "~~\\textbullet~".join(contact_parts) + "}",
        ]
    )


def _render_summary_block(summary: str) -> str:
    clean_summary = _clean_text(summary)
    if not clean_summary:
        return ""
    return "\n".join(
        [
            r"\section*{PROFESSIONAL SUMMARY}",
            _escape_latex(clean_summary),
            r"\vspace{0.18em}",
        ]
    )


def _render_education_block(education: list[dict[str, Any]]) -> str:
    if not education:
        return ""

    lines = [r"\section*{EDUCATION}"]
    for item in education:
        institution = _escape_latex(_clean_text(item.get("institution")))
        location = _clean_text(item.get("location"))
        years = _latex_date_cell(item.get("years"))
        raw_degree = _clean_text(item.get("degree")).replace(" – ", " - ").replace(" — ", " - ")
        degree = _escape_latex(raw_degree)
        description = _clean_text(item.get("description"))
        if description:
            degree = f"{degree} - {_escape_latex(description)}" if degree else _escape_latex(description)
        lines.append(
            r"\Entry{%s}{%s}{%s}{%s}"
            % (
                institution,
                f"-- {_escape_latex(location)}" if location else "",
                years,
                degree,
            )
        )
        lines.append(r"\vspace{0.16em}")
    return "\n".join(lines)


def _render_experience_block(experience: list[dict[str, Any]]) -> str:
    if not experience:
        return ""

    lines = [r"\section*{EXPERIENCE}"]
    for item in experience:
        company = _escape_latex(_clean_text(item.get("company")))
        location = _clean_text(item.get("location"))
        years = _latex_date_cell(item.get("years"))
        title = _escape_latex(_clean_text(item.get("title")))
        lines.append(
            r"\Entry{%s}{%s}{%s}{%s}"
            % (
                company,
                f"-- {_escape_latex(location)}" if location else "",
                years,
                title,
            )
        )
        lines.extend(_latex_bullet_list(item.get("description") or []))
        lines.append(r"\vspace{0.16em}")
    return "\n".join(lines).rstrip()


def _render_projects_block(projects: list[dict[str, Any]]) -> str:
    if not projects:
        return ""

    project_lines = [line for item in projects if (line := _project_line(item))]
    if not project_lines:
        return ""
    return "\n".join([r"\section*{PROJECTS}", *project_lines]).rstrip()


def _render_skills_block(
    technical_skills: list[str],
    awards: list[str],
) -> str:
    product_skills, tool_skills = _split_technical_skills(technical_skills)
    lines = [r"\section*{SKILLS}"]
    if product_skills:
        lines.append(
            r"\SkillLine{Product:}{%s}"
            % r" \textbar{} ".join(_escape_latex(skill) for skill in product_skills)
        )
    if tool_skills:
        lines.append(
            r"\SkillLine{Data \& Tools:}{%s}"
            % r" \textbar{} ".join(_escape_latex(skill) for skill in tool_skills)
        )
    if awards:
        lines.append(
            r"\SkillLine{Awards:}{%s}"
            % r" \textbar{} ".join(_escape_latex(item) for item in awards)
        )
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def generate_resume_latex(resume_data: dict[str, Any]) -> str:
    """Render resume data by filling the checked-in April 14 LaTeX master."""
    personal_info = resume_data.get("personalInfo") or {}
    additional = resume_data.get("additional") or {}
    technical_skills = [
        _clean_text(item)
        for item in (additional.get("technicalSkills") or [])
        if _clean_text(item)
    ]
    awards = [
        _clean_text(item)
        for item in (additional.get("awards") or [])
        if _clean_text(item)
    ]
    if not awards:
        awards = [
        _clean_text(item)
        for item in (additional.get("certificationsTraining") or [])
        if _clean_text(item)
        ]
    replacements = {
        "@@HEADER_BLOCK@@": _render_header_block(personal_info),
        "@@SUMMARY_BLOCK@@": _render_summary_block(resume_data.get("summary") or ""),
        "@@EDUCATION_BLOCK@@": _render_education_block(resume_data.get("education") or []),
        "@@EXPERIENCE_BLOCK@@": _render_experience_block(resume_data.get("workExperience") or []),
        "@@PROJECTS_BLOCK@@": _render_projects_block(resume_data.get("personalProjects") or []),
        "@@SKILLS_BLOCK@@": _render_skills_block(technical_skills, awards),
    }
    latex_source = _load_master_template()
    for placeholder, block in replacements.items():
        latex_source = latex_source.replace(placeholder, block)
    return latex_source


def render_resume_latex_text(
    resume_data: dict[str, Any],
    *,
    template_path: Path | None = None,
) -> str:
    """Backward-compatible alias for the text renderer."""
    del template_path
    return generate_resume_latex(resume_data)


async def render_latex_to_pdf(
    latex_source: str,
    *,
    filename_stem: str,
    page_size: str = "A4",
) -> bytes:
    """Render LaTeX to PDF with a local TeX compiler when available."""
    del page_size
    compiler = _find_compiler()
    if not compiler:
        raise PDFRenderError(
            "No TeX compiler was found. Install `tectonic`, `xelatex`, `pdflatex`, or `latexmk` "
            "to enable LaTeX PDF export."
        )

    temp_dir = Path(mkdtemp(prefix="resume-latex-pdf-"))
    try:
        def _build_pdf() -> str:
            tex_path = temp_dir / f"{filename_stem}.tex"
            tex_path.write_text(latex_source, encoding="utf-8")
            compiler_name = Path(compiler).name
            if compiler_name == "tectonic":
                command = [
                    compiler,
                    "-X",
                    "compile",
                    "--outdir",
                    str(temp_dir),
                    tex_path.name,
                ]
            elif compiler_name == "latexmk":
                command = [
                    compiler,
                    "-pdf",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-outdir=" + str(temp_dir),
                    tex_path.name,
                ]
            else:
                command = [
                    compiler,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(temp_dir),
                    tex_path.name,
                ]
            result = subprocess.run(
                command,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip() or "Unknown LaTeX compiler error"
                raise PDFRenderError(f"LaTeX PDF compilation failed: {stderr}")
            pdf_path = temp_dir / f"{filename_stem}.pdf"
            if not pdf_path.exists():
                raise PDFRenderError(
                    "LaTeX compiler did not produce a PDF file."
                )
            return str(pdf_path)

        pdf_path = await asyncio.to_thread(_build_pdf)
        return Path(pdf_path).read_bytes()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
