import json

from taskmaster.context_budget_manager import ContextBudgetManager, ContentType


def test_json_compression_and_retrieval(tmp_path):
    manager = ContextBudgetManager(db_path=tmp_path / "ctx.db", default_max_chars=500)
    payload = json.dumps({"items": [{"id": i, "name": f"item-{i}"} for i in range(100)]})

    result = manager.compress(payload, source_name="data.json")

    assert result.content_type == ContentType.JSON
    assert result.handle.startswith("ctx_")
    assert "retrieve handle" in result.compressed_text.lower()
    assert manager.retrieve(result.handle) == payload


def test_log_compression_keeps_errors(tmp_path):
    manager = ContextBudgetManager(db_path=tmp_path / "ctx.db", default_max_chars=800)
    payload = "\n".join(["INFO ok"] * 50 + ["ERROR broken module"] + ["INFO done"] * 50)

    result = manager.compress(payload, source_name="build.log")

    assert result.content_type == ContentType.LOG
    assert "ERROR broken module" in result.compressed_text


def test_code_compression_is_conservative(tmp_path):
    manager = ContextBudgetManager(db_path=tmp_path / "ctx.db", default_max_chars=5000)
    payload = "import os\n\ndef main():\n    return os.getcwd()\n"

    result = manager.compress(payload, source_name="app.py")

    assert result.content_type == ContentType.CODE
    assert "def main" in result.compressed_text


def test_core_prune(tmp_path, monkeypatch):
    import time
    import pytest
    
    manager = ContextBudgetManager(db_path=tmp_path / "ctx.db")
    
    monkeypatch.setattr(time, "time", lambda: 100.0)
    res1 = manager.compress("old message", source_name="old.txt")
    
    monkeypatch.setattr(time, "time", lambda: 200.0)
    res2 = manager.compress("new message", source_name="new.txt")
    
    # Prune elements older than 50 seconds relative to current time 200.0. Cutoff is 150.0.
    deleted = manager.prune(50.0)
    assert deleted == 1
    
    with pytest.raises(KeyError):
        manager.retrieve(res1.handle)
        
    assert manager.retrieve(res2.handle) == "new message"


def test_cli_prune(tmp_path, monkeypatch):
    import time
    import contextlib
    import io
    from taskmaster.cli import main
    from taskmaster.context_budget_manager.core import ContextBudgetManager
    
    db_file = tmp_path / "ctx.db"
    
    original_init = ContextBudgetManager.__init__
    def patched_init(self, db_path=None, default_max_chars=4000):
        original_init(self, db_path=db_file, default_max_chars=default_max_chars)
    
    monkeypatch.setattr(ContextBudgetManager, "__init__", patched_init)
    
    monkeypatch.setattr(time, "time", lambda: 100.0)
    main(["context", "compress", "tests/test_context_core.py"])
    
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["context", "prune", "--max-age-days", "0.005"])
        
    assert rc == 0
    assert "Successfully pruned 1" in buf.getvalue()



