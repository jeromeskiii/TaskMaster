"""TaskMaster compatibility package."""

from pathlib import Path


def _load_legacy_module() -> None:
    legacy_path = Path(__file__).resolve().parent.parent / "taskmaster.py"
    globals()["__file__"] = str(legacy_path)
    with legacy_path.open(encoding="utf-8") as legacy_file:
        legacy_code = compile(legacy_file.read(), str(legacy_path), "exec")
    exec(legacy_code, globals())


_load_legacy_module()
