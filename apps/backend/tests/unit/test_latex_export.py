"""Unit tests for the LaTeX resume exporter."""

from app.services.latex_export import generate_resume_latex
from app.routers.resumes import _extract_template_personal_info_from_markdown


def test_generate_resume_latex_preserves_template_style_links(sample_resume):
    source = generate_resume_latex(sample_resume)

    assert r"\href{https://janedoe.dev}{Portfolio}" in source
    assert r"\href{https://linkedin.com/in/janedoe}{LinkedIn}" in source
    assert r"\href{https://github.com/janedoe}{GitHub}" in source


def test_generate_resume_latex_preserves_name_casing(sample_resume):
    sample_resume["personalInfo"]["name"] = "Basher (Bash) Qatan"

    source = generate_resume_latex(sample_resume)

    assert "{Basher (Bash) Qatan}" in source
    assert "BASHER (BASH) QATAN" not in source


def test_generate_resume_latex_keeps_product_tools_out_of_data_tools(sample_resume):
    sample_resume["additional"]["technicalSkills"] = [
        "Agile Scrum",
        "PRD Writing",
        "Figma",
        "Jira",
        "Prototyping",
        "Lovable",
        "Bolt.New",
        "Automation",
        "API Integration",
        "SQL",
        "Python",
        "Pandas",
        "Data Visualization",
    ]

    source = generate_resume_latex(sample_resume)

    assert (
        r"\SkillLine{Product:}{Agile Scrum \textbar{} PRD Writing \textbar{} Figma"
        in source
    )
    assert "Lovable" in source
    assert "Bolt.New" in source
    assert (
        r"\SkillLine{Data \& Tools:}{SQL \textbar{} Python \textbar{} Pandas \textbar{} Data Visualization}"
        in source
    )


def test_generate_resume_latex_strips_trailing_periods_from_bullets(sample_resume):
    sample_resume["workExperience"][0]["description"] = [
        "Built a forecasting model.",
        "Improved onboarding conversion."
    ]

    source = generate_resume_latex(sample_resume)

    assert r"\item Built a forecasting model" in source
    assert r"\item Improved onboarding conversion" in source
    assert r"\item Built a forecasting model." not in source


def test_generate_resume_latex_omits_awards_section_line_when_empty(sample_resume):
    sample_resume["additional"]["awards"] = []

    source = generate_resume_latex(sample_resume)

    assert r"\section*{SKILLS}" in source
    assert "Awards:" not in source


def test_generate_resume_latex_keeps_projects_inline(sample_resume):
    source = generate_resume_latex(sample_resume)

    assert r"\section*{PROJECTS}" in source
    assert r"\ProjectLine{OpenAPI Generator}{" in source
    assert "Creator & Maintainer" not in source


def test_generate_resume_latex_keeps_education_before_experience(sample_resume):
    source = generate_resume_latex(sample_resume)

    assert source.index(r"\section*{EDUCATION}") < source.index(r"\section*{EXPERIENCE}")


def test_generate_resume_latex_separates_projects_with_spacing(sample_resume):
    source = generate_resume_latex(sample_resume)

    assert r"\newcommand{\ProjectLine}[2]{" in source
    assert r"\vspace{0.15em}" in source


def test_generate_resume_latex_abbreviates_month_names(sample_resume):
    sample_resume["workExperience"][0]["years"] = "January 2022 - May 2024"

    source = generate_resume_latex(sample_resume)

    assert r"\mbox{Jan~2022~-~May~2024}" in source
    assert "January 2022 - May 2024" not in source


def test_extract_template_personal_info_from_markdown_recovers_links():
    markdown = """
**BASHER (BASH) QATAN**

Los Angeles, CA  • qatanbash@gmail.com • [LinkedIn](http://linkedin.com/in/basher-qatan) • [Portfolio](http://bashqatan.notion.site)
"""

    extracted = _extract_template_personal_info_from_markdown(markdown)

    assert extracted["location"] == "Los Angeles, CA"
    assert extracted["email"] == "qatanbash@gmail.com"
    assert extracted["linkedin"] == "http://linkedin.com/in/basher-qatan"
    assert extracted["website"] == "http://bashqatan.notion.site"
