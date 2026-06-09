from taskmaster.context_budget_manager.core import ContextBudgetManager
from taskmaster import CACHE_DIR

def test_default_database_resolves_to_taskmaster_cache():
    manager = ContextBudgetManager()
    assert manager.store.db_path == CACHE_DIR / "context.db"
