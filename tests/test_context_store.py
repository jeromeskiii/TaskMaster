import sqlite3
from taskmaster.context_budget_manager.store import OriginalStore


class ConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        self.close_called = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        self.close_called = True
        self._conn.close()

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)


def test_store_put_and_get(tmp_path):
    db_file = tmp_path / "test.db"
    store = OriginalStore(db_file)
    
    handle = store.put("hello world", "text", "test.txt", {"meta": 1})
    assert handle.startswith("ctx_")
    
    content = store.get(handle)
    assert content == "hello world"


def test_store_stats(tmp_path):
    db_file = tmp_path / "test.db"
    store = OriginalStore(db_file)
    
    store.put("{}", "json", "a.json")
    store.put("[]", "json", "b.json")
    store.put("error", "log", "c.log")
    
    stats = store.stats()
    assert stats["total_originals"] == 3
    assert stats["by_type"] == {"json": 2, "log": 1}
    assert stats["db_path"] == str(db_file)


def test_connection_is_closed_after_put(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    store = OriginalStore(db_file)
    
    real_connect = store._connect
    connections = []

    def mock_connect():
        conn = real_connect()
        wrapper = ConnectionWrapper(conn)
        connections.append(wrapper)
        return wrapper

    monkeypatch.setattr(store, "_connect", mock_connect)
    
    store.put("test text", "text")
    
    assert len(connections) == 1
    # This assertion should FAIL in the current implementation because close() is never called
    assert connections[0].close_called is True


def test_connection_is_closed_after_get(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    store = OriginalStore(db_file)
    handle = store.put("test text", "text")
    
    real_connect = store._connect
    connections = []

    def mock_connect():
        conn = real_connect()
        wrapper = ConnectionWrapper(conn)
        connections.append(wrapper)
        return wrapper

    monkeypatch.setattr(store, "_connect", mock_connect)
    
    store.get(handle)
    
    assert len(connections) == 1
    # This assertion should FAIL in the current implementation because close() is never called
    assert connections[0].close_called is True


def test_store_prune(tmp_path, monkeypatch):
    import time
    import pytest
    
    db_file = tmp_path / "test.db"
    store = OriginalStore(db_file)
    
    # Mock time.time to simulate different insert times
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    h1 = store.put("old payload", "text")
    
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    h2 = store.put("new payload", "text")
    
    # Prune items older than 500 seconds (relative to current time 2000.0)
    # Cutoff = 2000.0 - 500.0 = 1500.0. h1 (1000.0) is pruned; h2 (2000.0) is kept.
    deleted = store.prune(500.0)
    assert deleted == 1
    
    with pytest.raises(KeyError):
        store.get(h1)
        
    assert store.get(h2) == "new payload"

