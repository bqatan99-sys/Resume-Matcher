"""Tests for template-backed field preservation."""

from app.routers.resumes import _preserve_template_source_fields


def test_preserve_template_source_fields_restores_project_slots_without_duplication():
    original_data = {
        "personalProjects": [
            {
                "name": "Pulse AI",
                "years": "Mar 2021 - Present",
                "role": "Lead PM",
                "description": ["Built and shipped Pulse as lead PM."],
            },
            {
                "name": "Spotify - Artists to Explore",
                "years": "2023 - 2024",
                "role": "Designer",
                "description": ["Designed a mobile feature for Spotify."],
            },
            {
                "name": "Google Maps - Tickets and Reservations",
                "years": "2023 - 2024",
                "role": "Designer",
                "description": ["Designed an integrated booking flow within Google Maps."],
            },
            {
                "name": "Trader Joe’s - Digital Transformation",
                "years": "2023 - 2024",
                "role": "Prototyper",
                "description": ["Prototyped a mobile-first loyalty and coupons experience."],
            },
        ]
    }
    improved_data = {
        "personalProjects": [
            {
                "name": "Gnome",
                "years": "Mar 2021 - Present",
                "role": "Lead PM",
                "description": [
                    "Built Gnome as lead PM.",
                    "Designed a mobile feature for Spotify.",
                    "Designed an integrated booking flow within Google Maps.",
                ],
            },
            {
                "name": "Trader Joe's - Digital Transformation",
                "years": "2024",
                "role": "Creator & Maintainer",
                "description": ["Prototyped a mobile-first loyalty and coupons experience."],
            },
        ]
    }

    result = _preserve_template_source_fields(original_data, improved_data)

    projects = result["personalProjects"]
    assert [project["name"] for project in projects] == [
        "Gnome",
        "Spotify - Artists to Explore",
        "Google Maps - Tickets and Reservations",
        "Trader Joe's - Digital Transformation",
    ]
    assert projects[1]["description"] == ["Designed a mobile feature for Spotify."]
    assert projects[2]["description"] == [
        "Designed an integrated booking flow within Google Maps."
    ]
    assert projects[3]["description"] == [
        "Prototyped a mobile-first loyalty and coupons experience."
    ]
