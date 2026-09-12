
"""Optional exports for DLC processor plugins.

This package may be imported in environments that do not install
`dlclivegui` (for example, DataJoint-only runtime images). In that case,
skip exporting dlclivegui-backed processors so unrelated imports continue
to work.
"""

from __future__ import annotations

import importlib

__all__: list[str] = []


def _export_if_available(module_name: str, symbol_name: str) -> None:
	try:
		module = importlib.import_module(f".{module_name}", __name__)
	except ModuleNotFoundError as exc:
		missing = (exc.name or "").split(".", 1)[0]
		if missing == "dlclivegui":
			return
		raise

	globals()[symbol_name] = getattr(module, symbol_name)
	__all__.append(symbol_name)


_export_if_available("dlcProcessor_dlconly", "dlc_only")
_export_if_available("dlc_processor_socket", "MyProcessor_socket")
_export_if_available("dlc_processor_socket_pd", "dlc_inference_w_pd")
_export_if_available("dlc_processor_socket_pd_sync", "dlc_inference_w_pd_sync")
_export_if_available("simple_processor", "TeensyLaser")
_export_if_available("processor_with_signal", "ProcessorWithSignal")