from chatbot.web_flow import format_source_link


def test_format_source_link():
    link = format_source_link(1, "Le Monde", "https://www.lemonde.fr/article")
    assert link == "1. [Le Monde](https://www.lemonde.fr/article)"
