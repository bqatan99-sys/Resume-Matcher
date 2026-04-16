from app.services.evidence_bank import build_evidence_bank_context


def test_build_evidence_bank_context_matches_current_employers() -> None:
    resume_data = {
        "workExperience": [
            {"company": "Anker Innovations"},
            {"company": "Qatana Consulting"},
        ],
        "personalProjects": [
            {"name": "Google Maps"},
        ],
    }
    job_keywords = {
        "required_skills": ["go-to-market", "customer discovery"],
        "preferred_skills": ["analytics"],
        "keywords": ["product strategy"],
    }

    context = build_evidence_bank_context(resume_data, job_keywords)

    assert "Anker Innovations" in context
    assert "Qatana Consulting" in context
    assert "summary_variants" in context
