from pathlib import Path


def test_build_visualizer_payload_csv(tmp_path):
    from app.core.logic import build_visualizer_payload

    fp = tmp_path / "table.csv"
    fp.write_text("Name;Value\nA;10\nB;25\n", encoding="utf-8")

    payload = build_visualizer_payload(fp)
    assert payload["kind"] == "sheet"
    assert payload["sheet"]["rows"] >= 2
    assert payload["sheet"]["cols"] >= 2
    assert isinstance(payload["layers"].get("heat"), list)


def test_build_visualizer_payload_text(tmp_path):
    from app.core.logic import build_visualizer_payload

    fp = tmp_path / "doc.txt"
    fp.write_text("Das ist ein Testdokument mit lokalem Inhalt.", encoding="utf-8")

    payload = build_visualizer_payload(fp)
    assert payload["kind"] == "text"
    assert "Testdokument" in payload["text"]["content"]


def test_summarize_visualizer_document_fallback(monkeypatch, tmp_path):
    import app.core.logic as logic

    class _FailingRequests:
        @staticmethod
        def post(*args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setitem(__import__("sys").modules, "requests", _FailingRequests)

    fp = tmp_path / "sum.txt"
    fp.write_text("Q1 Umsatz 500. Q2 Umsatz 650. Kosten 200.", encoding="utf-8")

    out = logic.summarize_visualizer_document(fp)
    assert "summary" in out
    assert out["source"]["name"] == "sum.txt"
    assert out["model"] in {"heuristic", "qwen2.5:0.5b"}
