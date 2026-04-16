import pytest

from app.services import portfolio_reader


def test_format_portfolio_context_without_evidence() -> None:
    assert portfolio_reader.format_portfolio_context(None) == "No portfolio evidence provided."


@pytest.mark.asyncio
async def test_load_portfolio_evidence_supports_notion_subdomain(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_complete_json(*args, **kwargs):
        return {
            "summary": "Product portfolio focused on feature ideation and execution.",
            "transferable_skills": ["Customer discovery", "Product strategy"],
            "projects": [
                {
                    "name": "Google Maps Feature Revision - Ticket and Reservations",
                    "tools": ["Figma", "Notion"],
                    "outcomes": ["Reduced redirect friction"],
                    "evidence": ["Designed an integrated booking flow"],
                    "role_hint": "Designer",
                }
            ],
        }

    monkeypatch.setattr(
        portfolio_reader,
        "_fetch_public_page",
        lambda url: ("Projects and Blog", "Google Maps ticketing flow and Trader Joe's digitization"),
    )
    monkeypatch.setattr(portfolio_reader, "complete_json", fake_complete_json)

    result = await portfolio_reader.load_portfolio_evidence("https://bashqatan.notion.site")

    assert result["source_type"] == "notion"
    assert result["source_url"] == "https://bashqatan.notion.site"
    assert result["projects"][0]["name"] == "Google Maps Feature Revision - Ticket and Reservations"
    assert "Customer discovery" in result["transferable_skills"]
