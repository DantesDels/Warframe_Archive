"""Lazy package facade (PEP 562) for packages with heavy dependencies.

Single responsibility: resolve a facade's public names on FIRST access, so
importing the package never drags the whole dependency stack into every
consumer.  The Discord bot needs three guard texts and two query probes from
``engram.rag``; without this it also loaded SQLAlchemy, the DB models and the
retrieval stack — one broken module there took the whole bot down.

Usage (inside a package ``__init__.py``)::

    import sys
    from ..lazy_facade import install

    install(sys.modules[__name__], {"RAGService": ".service", ...})

``from package import NAME`` keeps working unchanged, and each name is imported
once then cached on the module.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType


def install(module: ModuleType, exports: dict[str, str]) -> None:
    """Wire ``__getattr__`` / ``__dir__`` / ``__all__`` of ``module``.

    ``exports`` maps each public name to the relative module defining it.
    """

    def resolve(name: str):
        target = exports.get(name)
        if target is None:
            raise AttributeError(
                f"module {module.__name__!r} has no attribute {name!r}")
        value = getattr(import_module(target, module.__name__), name)
        setattr(module, name, value)        # cache: one import per name
        return value

    module.__getattr__ = resolve            # type: ignore[attr-defined]
    module.__dir__ = lambda: sorted(exports)  # type: ignore[attr-defined]
    module.__all__ = sorted(exports)


__all__ = ["install"]
