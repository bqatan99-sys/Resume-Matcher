"""Integration tests for resume CRUD endpoints."""

import base64
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mock_resume_record(sample_resume):
    """A resume DB record with all fields."""
    return {
        "resume_id": "res-123",
        "content": "# Jane Doe\nSenior Backend Engineer",
        "content_type": "md",
        "filename": "resume.pdf",
        "is_master": True,
        "parent_id": None,
        "processed_data": sample_resume,
        "processing_status": "ready",
        "cover_letter": None,
        "outreach_message": None,
        "title": None,
        "original_markdown": "# Jane Doe\nSenior Backend Engineer",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


class TestGetResume:
    """GET /api/v1/resumes?resume_id=..."""

    @patch("app.routers.resumes.db")
    async def test_fetch_existing_resume(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        async with client:
            resp = await client.get("/api/v1/resumes", params={"resume_id": "res-123"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["resume_id"] == "res-123"
        assert data["processed_resume"] is not None
        assert data["processed_resume"]["summary"] != ""
        assert data["has_template_docx"] is False

    @patch("app.routers.resumes.db")
    async def test_fetch_nonexistent_returns_404(self, mock_db, client):
        mock_db.get_resume.return_value = None
        async with client:
            resp = await client.get("/api/v1/resumes", params={"resume_id": "nonexistent"})
        assert resp.status_code == 404


class TestListResumes:
    """GET /api/v1/resumes/list"""

    @patch("app.routers.resumes.db")
    async def test_list_excludes_master_by_default(self, mock_db, client):
        mock_db.list_resumes.return_value = [
            {"resume_id": "master", "is_master": True, "created_at": "2026-01-01", "updated_at": "2026-01-01"},
            {"resume_id": "tailored-1", "is_master": False, "created_at": "2026-01-02", "updated_at": "2026-01-02"},
        ]
        async with client:
            resp = await client.get("/api/v1/resumes/list")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["resume_id"] == "tailored-1"

    @patch("app.routers.resumes.db")
    async def test_list_includes_master_when_requested(self, mock_db, client):
        mock_db.list_resumes.return_value = [
            {"resume_id": "master", "is_master": True, "created_at": "2026-01-01", "updated_at": "2026-01-01"},
            {"resume_id": "tailored-1", "is_master": False, "created_at": "2026-01-02", "updated_at": "2026-01-02"},
        ]
        async with client:
            resp = await client.get("/api/v1/resumes/list", params={"include_master": True})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2


class TestDeleteResume:
    """DELETE /api/v1/resumes/{resume_id}"""

    @patch("app.routers.resumes.db")
    async def test_delete_existing_resume(self, mock_db, client):
        mock_db.delete_resume.return_value = True
        async with client:
            resp = await client.delete("/api/v1/resumes/res-123")
        assert resp.status_code == 200

    @patch("app.routers.resumes.db")
    async def test_delete_nonexistent_returns_404(self, mock_db, client):
        mock_db.delete_resume.return_value = False
        async with client:
            resp = await client.delete("/api/v1/resumes/nonexistent")
        assert resp.status_code == 404


class TestUpdateTitle:
    """PATCH /api/v1/resumes/{resume_id}/title"""

    @patch("app.routers.resumes.db")
    async def test_update_title(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        mock_db.update_resume.return_value = {**mock_resume_record, "title": "New Title"}
        async with client:
            resp = await client.patch("/api/v1/resumes/res-123/title", json={"title": "New Title"})
        assert resp.status_code == 200

    @patch("app.routers.resumes.db")
    async def test_update_title_nonexistent_returns_404(self, mock_db, client):
        mock_db.get_resume.return_value = None
        async with client:
            resp = await client.patch("/api/v1/resumes/nonexistent/title", json={"title": "X"})
        assert resp.status_code == 404


class TestUpdateCoverLetter:
    """PATCH /api/v1/resumes/{resume_id}/cover-letter"""

    @patch("app.routers.resumes.db")
    async def test_update_cover_letter(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        mock_db.update_resume.return_value = {**mock_resume_record, "cover_letter": "Dear hiring manager..."}
        async with client:
            resp = await client.patch("/api/v1/resumes/res-123/cover-letter", json={"content": "Dear hiring manager..."})
        assert resp.status_code == 200


class TestUpdateOutreachMessage:
    """PATCH /api/v1/resumes/{resume_id}/outreach-message"""

    @patch("app.routers.resumes.db")
    async def test_update_outreach(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        mock_db.update_resume.return_value = {**mock_resume_record, "outreach_message": "Hi, I saw your posting..."}
        async with client:
            resp = await client.patch("/api/v1/resumes/res-123/outreach-message", json={"content": "Hi, I saw your posting..."})
        assert resp.status_code == 200


class TestRetryProcessing:
    """POST /api/v1/resumes/{resume_id}/retry-processing"""

    @patch("app.routers.resumes.parse_resume_to_json", new_callable=AsyncMock)
    @patch("app.routers.resumes.db")
    async def test_retry_successful(self, mock_db, mock_parse, client, mock_resume_record, sample_resume):
        failed_record = {**mock_resume_record, "processing_status": "failed"}
        mock_db.get_resume.return_value = failed_record
        mock_parse.return_value = sample_resume
        mock_db.update_resume.return_value = {**failed_record, "processing_status": "ready", "processed_data": sample_resume}
        async with client:
            resp = await client.post("/api/v1/resumes/res-123/retry-processing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "ready"

    @patch("app.routers.resumes.db")
    async def test_retry_not_failed_returns_400(self, mock_db, client, mock_resume_record):
        # processing_status is "ready", not "failed"
        mock_db.get_resume.return_value = mock_resume_record
        async with client:
            resp = await client.post("/api/v1/resumes/res-123/retry-processing")
        assert resp.status_code == 400


class TestDownloadResumeDocx:
    """GET /api/v1/resumes/{resume_id}/docx"""

    @patch("app.routers.resumes.db")
    async def test_download_resume_docx(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        async with client:
            resp = await client.get("/api/v1/resumes/res-123/docx")

        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert 'filename="resume_res-123.docx"' in resp.headers["content-disposition"]
        assert resp.content[:2] == b"PK"

    @patch("app.routers.resumes.db")
    async def test_download_resume_docx_uses_parent_template(
        self, mock_db, client, mock_resume_record
    ):
        template = base64.b64encode(b"template-bytes").decode("ascii")
        child_record = {
            **mock_resume_record,
            "resume_id": "child-123",
            "parent_id": "parent-123",
        }
        parent_record = {
            **mock_resume_record,
            "resume_id": "parent-123",
            "template_docx_base64": template,
        }

        def get_resume_side_effect(resume_id):
            if resume_id == "child-123":
                return child_record
            if resume_id == "parent-123":
                return parent_record
            return None

        mock_db.get_resume.side_effect = get_resume_side_effect

        async with client:
            resp = await client.get("/api/v1/resumes/child-123/docx")

        assert resp.status_code == 409
        assert "LaTeX master template" in resp.json()["detail"]


class TestDownloadResumeTex:
    """GET /api/v1/resumes/{resume_id}/tex"""

    @patch("app.routers.resumes.db")
    async def test_download_resume_tex(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record

        async with client:
            resp = await client.get("/api/v1/resumes/res-123/tex")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-tex")
        assert 'filename="resume_res-123.tex"' in resp.headers["content-disposition"]
        assert "\\documentclass" in resp.text


class TestDownloadResumePdf:
    """GET /api/v1/resumes/{resume_id}/pdf"""

    @patch("app.routers.resumes.db")
    @patch("app.routers.resumes.render_latex_to_pdf", new_callable=AsyncMock)
    async def test_download_resume_pdf_uses_template_backed_export(
        self, mock_render_latex_pdf, mock_db, client, mock_resume_record
    ):
        mock_render_latex_pdf.return_value = b"%PDF-template"
        mock_db.get_resume.return_value = {
            **mock_resume_record,
            "template_docx_base64": "ZmFrZS10ZW1wbGF0ZQ==",
        }
        async with client:
            resp = await client.get("/api/v1/resumes/res-123/pdf")

        assert resp.status_code == 200
        assert resp.content == b"%PDF-template"
        assert resp.headers["content-type"] == "application/pdf"
        mock_render_latex_pdf.assert_called_once()


class TestAttachResumeTemplate:
    """POST /api/v1/resumes/{resume_id}/template"""

    @patch("app.routers.resumes.db")
    async def test_attach_resume_template(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record
        mock_db.update_resume.return_value = {**mock_resume_record, "template_docx_base64": "abc"}

        files = {
            "file": (
                "template.docx",
                b"fake-docx-content",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        async with client:
            resp = await client.post("/api/v1/resumes/res-123/template", files=files)

        assert resp.status_code == 200
        assert "attached successfully" in resp.json()["message"]
        update_payload = mock_db.update_resume.call_args.args[1]
        assert "template_docx_base64" in update_payload

    @patch("app.routers.resumes.db")
    async def test_attach_resume_template_rejects_non_docx(self, mock_db, client, mock_resume_record):
        mock_db.get_resume.return_value = mock_resume_record

        files = {"file": ("template.pdf", b"nope", "application/pdf")}
        async with client:
            resp = await client.post("/api/v1/resumes/res-123/template", files=files)

        assert resp.status_code == 400
