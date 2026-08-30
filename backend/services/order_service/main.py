"""Order service entrypoint."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("tastekart_order_service_legacy", Path(__file__).parents[1] / "order_service.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
app = _module.app

__all__ = ["app"]
