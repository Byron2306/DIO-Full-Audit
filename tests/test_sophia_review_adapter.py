from adapters.sophia.review_pipeline import (
    _allowed_citation_keys,
    extract_in_text_citations,
    parse_reference_entries,
    reference_key,
    split_reference_section,
    validate_gemini_commentary,
)


def test_reference_section_and_entries() -> None:
    body, references = split_reference_section(
        "A claim (Smith, 2020).\n\n## References\n\nSmith, J. (2020). A title. Journal, 1(2), 1-4."
    )
    assert "A claim" in body
    entries = parse_reference_entries(references)
    assert len(entries) == 1
    assert reference_key(entries[0]) == "smith:2020"


def test_in_text_citation_keys_are_deduplicated() -> None:
    rows = extract_in_text_citations(
        "Smith and Patel (2020) found one result. A later review agreed (Smith & Patel, 2020; Jones et al., 2021)."
    )
    assert [row["key"] for row in rows] == ["jones:2021", "smith:2020"]


def test_gemini_commentary_validation_accepts_grounded_lane_output() -> None:
    result = {
        "source": "reasoned_integrity_lane",
        "reasoned_provider": "gemini",
        "reasoned_provider_status": "ok",
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
    }
    validation = validate_gemini_commentary(
        "## Major revisions\nThe method is unspecified in [P2]; narrow the causal claim in [C1].",
        result,
        {"P1", "P2", "C1"},
        {"smith:2020"},
        set(),
    )
    assert validation["passed"] is True


def test_gemini_commentary_validation_rejects_invented_citation() -> None:
    result = {
        "source": "reasoned_integrity_lane",
        "reasoned_provider": "gemini",
        "reasoned_provider_status": "ok",
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
    }
    validation = validate_gemini_commentary(
        "[P1] should be compared with Invented (2026), doi:10.9999/not-real.",
        result,
        {"P1"},
        set(),
        set(),
    )
    assert validation["passed"] is False
    assert validation["unknown_citations"] == ["invented:2026"]
    assert validation["unknown_dois"] == ["10.9999/not-real"]


def test_allowed_citation_keys_include_reference_coauthors() -> None:
    audit = {
        "in_text_citations": [],
        "reference_entries": [{
            "key": "carless:2018",
            "entry": "Carless, D., & Boud, D. (2018). The development of student feedback literacy.",
        }],
    }
    assert _allowed_citation_keys(audit, []) >= {"carless:2018", "boud:2018"}

def test_pdf_small_caps_reference_boundary_and_bare_years() -> None:
    body, references = split_reference_section(
        """
A manuscript claim (Abdou et al., 2021).

R EFERENCES

Mostafa Abdou, Artur Kulmizev, Daniel Hershcovich, Stella Frank, Ellie Pavlick, and Anders
Søgaard. Can language models encode perceptual structure without grounding? a case study
in color. arXiv preprint arXiv:2109.06129, 2021.
Guillaume Alain and Yoshua Bengio. Understanding intermediate layers using linear classifier
probes. arXiv preprint arXiv:1610.01644, 2016.

10
Preprint

NYC OpenData. Points of interest, 2023. URL https://example.invalid/data.

A DATASETS

The appendix contains a real scholarly sentence that must remain in the body.
""".strip()
    )

    assert "A manuscript claim" in body
    assert "A DATASETS" in body
    assert "appendix contains" in body
    assert "A DATASETS" not in references

    entries = parse_reference_entries(references)
    keys = [reference_key(entry) for entry in entries]

    assert keys == ["abdou:2021", "alain:2016", "opendata:2023"]
    assert all(entry.strip() != "Preprint" for entry in entries)


def test_reference_key_does_not_treat_arxiv_identifier_as_year() -> None:
    entry = (
        "Yonatan Bisk, Ari Holtzman, Jesse Thomason, Jacob Andreas, Yoshua Bengio, "
        "Joyce Chai, Mirella Lapata, Angeliki Lazaridou, Jonathan May, Aleksandr "
        "Nisnevich, et al. Experience grounds language. "
        "arXiv preprint arXiv:2004.10151, 2020."
    )
    assert reference_key(entry) == "bisk:2020"


def test_review_paragraphs_exclude_bibliography_and_pdf_furniture() -> None:
    from adapters.sophia.review_pipeline import _review_paragraphs

    text = """
A sufficiently long manuscript paragraph states the research problem and its evidence boundary.

12
Preprint

R EFERENCES
Mostafa Abdou and Anders Søgaard. Example scholarly reference, 2021.

A DATASETS
A sufficiently long appendix paragraph describes the dataset construction and its limitations.
""".strip()

    spans = _review_paragraphs(text)
    joined = "\n".join(row["quote"] for row in spans)

    assert "research problem" in joined
    assert "dataset construction" in joined
    assert "Mostafa Abdou" not in joined
    assert "Preprint" not in joined

def test_single_author_reference_lines_split_before_year_is_visible() -> None:
    references = """
Jack Bandy. Three decades of new york times headlines, 2021. URL https://www.kaggle.
com/datasets/johnbandy/new-york-times-headlines. Kaggle dataset.
Yonatan Belinkov. Probing classifiers: Promises, shortcomings, and advances. Computational
Linguistics, 48(1):207–219, 2022.
Emily M Bender and Alexander Koller. Climbing towards nlu: On meaning, form, and
understanding in the age of data. Proceedings of ACL, 2020.
""".strip()

    entries = parse_reference_entries(references)
    assert [reference_key(entry) for entry in entries] == [
        "bandy:2021",
        "belinkov:2022",
        "bender:2020",
    ]


def test_pdf_claim_cleanup_removes_front_matter_and_section_headings() -> None:
    from adapters.sophia.review_pipeline import _clean_pdf_layout_text

    raw = """
L ANGUAGE M ODELS R EPRESENT S PACE AND T IME
Wes Gurnee & Max Tegmark
Massachusetts Institute of Technology
{wesg, tegmark}@mit.edu
A BSTRACT
The capabilities of large language models have sparked debate over what they represent.

3.2 L INEAR R EPRESENTATIONS
Within the interpretability literature, there is evidence supporting a linear representation hypothesis.

Figure 2: Out-of-sample results for all models.
Dataset        Model        Score
World          Llama        0.81
""".strip()

    cleaned = _clean_pdf_layout_text(raw, drop_table_lines=True)

    assert "Wes Gurnee" not in cleaned
    assert "A BSTRACT" not in cleaned
    assert "3.2 L INEAR R EPRESENTATIONS" not in cleaned
    assert "Figure 2:" not in cleaned
    assert "Dataset        Model" not in cleaned
    assert "capabilities of large language models" in cleaned
    assert "linear representation hypothesis" in cleaned


def test_reference_year_ignores_url_and_version_metadata_years() -> None:
    elhage = (
        "Nelson Elhage, Tristan Hume, Catherine Olsson, Neel Nanda, Tom Henighan. "
        "Softmax linear units. Transformer Circuits Thread, 2022a. "
        "https://transformer-circuits.pub/2022/solu/index.html."
    )
    lehmann = (
        "Jens Lehmann, Robert Isele, Max Jakob, Anja Jentzsch, Dimitris Kontokostas, "
        "and Christian Bizer. Dbpedia - a large-scale, multilingual knowledge base "
        "extracted from wikipedia, 2015. URL http://dbpedia.org. Version 2023."
    )

    assert reference_key(elhage) == "elhage:2022a"
    assert reference_key(lehmann) == "lehmann:2015"


def test_reference_parser_keeps_wrapped_conference_title_with_rauker() -> None:
    references = """
Tilman Räuker, Anson Ho, Stephen Casper, and Dylan Hadfield-Menell. Toward transparent ai:
A survey on interpreting the inner structures of deep neural networks. In 2023 IEEE Conference on
Secure and Trustworthy Machine Learning (SaTML), pp. 464–483. IEEE, 2023.
Abhilasha Ravichander, Yonatan Belinkov, and Eduard Hovy. Probing the probing paradigm:
Does probing accuracy entail task relevance? arXiv preprint arXiv:2005.00719, 2020.
""".strip()

    entries = parse_reference_entries(references)
    keys = [reference_key(entry) for entry in entries]

    assert keys == ["rauker:2023", "ravichander:2020"]
    assert all(not key.startswith("secure:") for key in keys)


def test_in_text_citations_normalize_unicode_hyphenation_corporate_and_suffixes() -> None:
    body = """
The biological analogy is discussed by (Buzsáki & Llinás, 2017).
Sparse autoencoders may help (Cunning-
ham et al., 2023).
Related interpretability work includes (Räuker et al., 2023).
Prior geographic probing includes (Liétard et al., 2021).
The city dataset follows (NYC OpenData, 2023).
Factual recall work is summarized by (Meng et al., 2022a;b; Geva et al., 2023).
Lehmann et al. (2015) describes DBpedia.
""".strip()

    keys = {row["key"] for row in extract_in_text_citations(body)}

    assert "buzsaki:2017" in keys
    assert "cunningham:2023" in keys
    assert "rauker:2023" in keys
    assert "lietard:2021" in keys
    assert "opendata:2023" in keys
    assert "meng:2022a" in keys
    assert "meng:2022b" in keys
    assert "geva:2023" in keys
    assert "lehmann:2015" in keys

    assert "buzsa:2017" not in keys
    assert "cunning:2023" not in keys
    assert "ra:2023" not in keys
    assert "nyc:2023" not in keys

def test_in_text_citation_extractor_rejects_numeric_threshold_as_fake_citation() -> None:
    body = (
        "We filter out zipcodes with fewer than 10000 "
        "(or with population density greater than 50 and population greater than 2000), "
        "and retain the remaining observations. "
        "Prior work is discussed by (Buzsaki & Llinas, 2017)."
    )
    keys = {row["key"] for row in extract_in_text_citations(body)}

    assert "than:2000" not in keys
    assert "buzsaki:2017" in keys
