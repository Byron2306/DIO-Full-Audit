from pathlib import Path

from presence_core.router import route_message


ROUTES = Path("config/routes.json")


def test_finance_readiness_imperative_routes_to_intake():
    decision = route_message(
        "Assess whether my business evidence is ready for a finance application and show me what is missing.",
        "public",
        ROUTES,
    )
    assert decision.product == "finance_readiness_studio"
    assert decision.intent == "intake_request"
    assert decision.source == "deterministic"


def test_article_publication_imperative_routes_to_intake():
    decision = route_message(
        "Turn these supplied sources into a publication-ready article draft with traceable claims and references.",
        "public",
        ROUTES,
    )
    assert decision.product == "article_publication_studio"
    assert decision.intent == "intake_request"
    assert decision.source == "deterministic"


def test_polite_imperatives_also_route_to_intake():
    finance = route_message(
        "Could you assess whether my finance readiness evidence is complete?",
        "public",
        ROUTES,
    )
    article = route_message(
        "Please turn these sources into an Article Studio draft.",
        "public",
        ROUTES,
    )
    assert (finance.product, finance.intent) == ("finance_readiness_studio", "intake_request")
    assert (article.product, article.intent) == ("article_publication_studio", "intake_request")


def test_informational_studio_questions_do_not_become_intake():
    finance = route_message("What does Finance Readiness Studio do?", "public", ROUTES)
    article = route_message("Tell me about Article Studio.", "public", ROUTES)
    assert (finance.product, finance.intent) == ("finance_readiness_studio", "product_info")
    assert (article.product, article.intent) == ("article_publication_studio", "product_info")


def test_specific_article_studio_phrase_beats_broad_article_keyword():
    studio = route_message("Tell me about Article Studio.", "public", ROUTES)
    generic = route_message("Write an article for our newsletter.", "public", ROUTES)
    assert (studio.product, studio.intent) == ("article_publication_studio", "product_info")
    assert (generic.product, generic.intent) == ("nichefoundry", "intake_request")
