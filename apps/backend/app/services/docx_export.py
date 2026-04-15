"""DOCX export helpers with optional source-template reuse."""

from io import BytesIO
from typing import Any

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


NAME_FONT_SIZE = Pt(16)
CONTACT_FONT_SIZE = Pt(9)
BODY_FONT_SIZE = Pt(10)
SECTION_FONT_SIZE = Pt(10)


def _set_run_font(run: Any, size: Pt, *, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run.font.size = size
    run.bold = bold
    run.italic = italic


def _set_bottom_border(paragraph: Any, color: str = "000000", size: str = "6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)

    for edge in ("top", "left", "right", "between"):
        existing = borders.find(qn(f"w:{edge}"))
        if existing is None:
            existing = OxmlElement(f"w:{edge}")
            existing.set(qn("w:val"), "none")
            existing.set(qn("w:sz"), "0")
            existing.set(qn("w:space"), "0")
            existing.set(qn("w:color"), "000000")
            borders.append(existing)

    bottom = borders.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        borders.append(bottom)
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "0")
    bottom.set(qn("w:color"), color)


def _prepare_document(template_bytes: bytes | None = None) -> tuple[DocumentType, int]:
    document = Document(BytesIO(template_bytes)) if template_bytes else Document()
    section = document.sections[0]

    if not template_bytes:
        section.top_margin = Inches(0.39)
        section.bottom_margin = Inches(0.39)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
        normal = document.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = BODY_FONT_SIZE

    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    content_width = int(section.page_width - section.left_margin - section.right_margin)
    return document, content_width


def _add_name_header(document: DocumentType, personal_info: dict[str, Any]) -> None:
    name = (personal_info.get("name") or "").strip()
    if not name:
        return

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    _set_bottom_border(paragraph, color="FFFFFF", size="6")

    run = paragraph.add_run(name.upper())
    _set_run_font(run, NAME_FONT_SIZE, bold=True)


def _add_contact_header(document: DocumentType, personal_info: dict[str, Any]) -> None:
    parts: list[str] = []
    location = (personal_info.get("location") or "").strip()
    email = (personal_info.get("email") or "").strip()
    phone = (personal_info.get("phone") or "").strip()
    linkedin = (personal_info.get("linkedin") or "").strip()
    website = (personal_info.get("website") or "").strip()
    github = (personal_info.get("github") or "").strip()

    if location:
        parts.append(location)
    if phone:
        parts.append(phone)
    if email:
        parts.append(email)
    if linkedin:
        parts.append("LinkedIn")
    if website:
        parts.append("Portfolio")
    if github:
        parts.append("GitHub")

    if not parts:
        return

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    _set_bottom_border(paragraph, color="FFFFFF", size="6")

    run = paragraph.add_run(" \u2022 ".join(parts))
    _set_run_font(run, CONTACT_FONT_SIZE)


def _add_spacer(document: DocumentType, size: int = 2) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(size)
    paragraph.paragraph_format.line_spacing = 1
    paragraph.add_run("")


def _add_section_heading(document: DocumentType, heading: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    _set_bottom_border(paragraph)

    run = paragraph.add_run(heading.upper())
    _set_run_font(run, SECTION_FONT_SIZE, bold=True)


def _add_body_paragraph(document: DocumentType, text: str, *, italic: bool = False) -> None:
    if not text.strip():
        return
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    run = paragraph.add_run(text.strip())
    _set_run_font(run, BODY_FONT_SIZE, italic=italic)


def _add_titled_date_row(
    document: DocumentType,
    content_width: int,
    left_main: str,
    left_suffix: str = "",
    right_text: str = "",
) -> None:
    if not left_main and not left_suffix and not right_text:
        return

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    paragraph.paragraph_format.tab_stops.add_tab_stop(content_width, WD_TAB_ALIGNMENT.RIGHT)

    if left_main:
        run = paragraph.add_run(left_main)
        _set_run_font(run, BODY_FONT_SIZE, bold=True)
    if left_suffix:
        run = paragraph.add_run(left_suffix)
        _set_run_font(run, BODY_FONT_SIZE)
    if right_text:
        paragraph.add_run("\t")
        run = paragraph.add_run(right_text)
        _set_run_font(run, BODY_FONT_SIZE, bold=True)


def _add_summary_section(document: DocumentType, summary: str) -> None:
    summary = summary.strip()
    if not summary:
        return
    _add_section_heading(document, "Professional Summary")
    _add_spacer(document)
    _add_body_paragraph(document, summary)
    _add_spacer(document)


def _add_education_section(
    document: DocumentType, content_width: int, education_items: list[dict[str, Any]]
) -> None:
    if not education_items:
        return

    _add_section_heading(document, "Education")
    _add_spacer(document)
    for education in education_items:
        institution = (education.get("institution") or "").strip()
        location = (education.get("location") or "").strip()
        years = (education.get("years") or "").strip()
        degree = (education.get("degree") or "").strip()
        left_suffix = f" - {location}" if location else ""
        _add_titled_date_row(document, content_width, institution, left_suffix, years)
        _add_body_paragraph(document, degree, italic=True)
        description = education.get("description")
        if isinstance(description, str) and description.strip():
            _add_body_paragraph(document, description)
        elif isinstance(description, list):
            for line in description:
                _add_body_paragraph(document, str(line))
        _add_spacer(document)


def _add_experience_section(
    document: DocumentType, content_width: int, experiences: list[dict[str, Any]]
) -> None:
    if not experiences:
        return

    _add_section_heading(document, "Experience")
    _add_spacer(document)
    for experience in experiences:
        company = (experience.get("company") or "").strip()
        location = (experience.get("location") or "").strip()
        years = (experience.get("years") or "").strip()
        title = (experience.get("title") or "").strip()
        left_suffix = f" - {location}" if location else ""
        _add_titled_date_row(document, content_width, company, left_suffix, years)
        _add_body_paragraph(document, title)
        for line in experience.get("description") or []:
            _add_body_paragraph(document, str(line))
        _add_spacer(document)


def _add_projects_section(document: DocumentType, projects: list[dict[str, Any]]) -> None:
    if not projects:
        return

    _add_section_heading(document, "Projects")
    _add_spacer(document)
    for project in projects:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1

        name = str(project.get("name") or "").strip()
        if name:
            run = paragraph.add_run(name)
            _set_run_font(run, BODY_FONT_SIZE, bold=True)

        details = [
            str(item).strip()
            for item in (project.get("description") or [])
            if str(item).strip()
        ]
        years = str(project.get("years") or "").strip()
        if years:
            details.append(years)
        detail_text = " | ".join(details)
        if detail_text:
            if name:
                run = paragraph.add_run(": ")
                _set_run_font(run, BODY_FONT_SIZE)
            run = paragraph.add_run(detail_text)
            _set_run_font(run, BODY_FONT_SIZE)
    _add_spacer(document)


def _add_additional_section(document: DocumentType, additional: dict[str, Any]) -> None:
    if not additional:
        return

    rows = [
        ("Technical Skills", additional.get("technicalSkills") or []),
        ("Languages", additional.get("languages") or []),
        ("Certifications", additional.get("certificationsTraining") or []),
        ("Awards", additional.get("awards") or []),
    ]
    rows = [(label, values) for label, values in rows if values]
    if not rows:
        return

    _add_section_heading(document, "Skills")
    _add_spacer(document)
    for label, values in rows:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1
        run = paragraph.add_run(f"{label}: ")
        _set_run_font(run, BODY_FONT_SIZE, bold=True)
        run = paragraph.add_run(
            " | ".join(str(value).strip() for value in values if str(value).strip())
        )
        _set_run_font(run, BODY_FONT_SIZE)


def _add_custom_sections(
    document: DocumentType, content_width: int, resume_data: dict[str, Any]
) -> None:
    custom_sections = resume_data.get("customSections") or {}
    section_meta = resume_data.get("sectionMeta") or []
    for meta in sorted(section_meta, key=lambda item: item.get("order", 999)):
        if meta.get("isDefault") or not meta.get("isVisible"):
            continue
        key = meta.get("key")
        section = custom_sections.get(key)
        if not section:
            continue

        _add_section_heading(document, meta.get("displayName") or key or "Section")
        _add_spacer(document)
        section_type = section.get("sectionType")
        if section_type == "text":
            _add_body_paragraph(document, str(section.get("text") or ""))
        elif section_type == "stringList":
            for item in section.get("strings") or []:
                _add_body_paragraph(document, str(item))
        elif section_type == "itemList":
            for item in section.get("items") or []:
                title = str(item.get("title") or "").strip()
                subtitle = str(item.get("subtitle") or "").strip()
                location = str(item.get("location") or "").strip()
                years = str(item.get("years") or "").strip()
                left_suffix = f" - {location}" if location else ""
                _add_titled_date_row(document, content_width, title, left_suffix, years)
                if subtitle:
                    _add_body_paragraph(document, subtitle, italic=True)
                for line in item.get("description") or []:
                    _add_body_paragraph(document, str(line))
                _add_spacer(document)
        _add_spacer(document)


def generate_resume_docx_bytes(
    resume_data: dict[str, Any], template_bytes: bytes | None = None
) -> bytes:
    """Build a DOCX resume, reusing the original uploaded template when available."""
    document, content_width = _prepare_document(template_bytes)

    personal_info = resume_data.get("personalInfo") or {}
    _add_name_header(document, personal_info)
    _add_contact_header(document, personal_info)
    _add_spacer(document, size=6)

    _add_summary_section(document, str(resume_data.get("summary") or ""))
    _add_education_section(document, content_width, resume_data.get("education") or [])
    _add_experience_section(document, content_width, resume_data.get("workExperience") or [])
    _add_projects_section(document, resume_data.get("personalProjects") or [])
    _add_additional_section(document, resume_data.get("additional") or {})
    _add_custom_sections(document, content_width, resume_data)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
