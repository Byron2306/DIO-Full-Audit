from pathlib import Path
import importlib.util


SERVER = (
    Path(__file__).resolve().parents[1]
    / "cross_folder_variants"
    / "Integritas-Mechanicus"
    / "A_CODE"
    / "arda_os"
    / "backend"
    / "services"
    / "presence_server.py"
)


def _load_presence_server():
    spec = importlib.util.spec_from_file_location(
        "dio_sophia_presence_server",
        SERVER,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dio_product_review_request_has_distinct_execution_contract():
    server = _load_presence_server()

    assert hasattr(
        server,
        "_is_dio_product_review_task",
    ), "DIO Sophia product review routing helper is missing"

    body = {
        "dio_product_review_lane": True,
        "reasoned_integrity_lane": True,
        "reasoned_provider": "local",
        "document_evidence_task": "dio_sophia_academic_review",
    }
    client_context = {
        "ui_surface": "dio_sophia_review",
    }

    assert server._is_dio_product_review_task(
        body=body,
        client_context=client_context,
        document_evidence={"documents": [{"source_name": "paper.pdf"}]},
    ) is True
