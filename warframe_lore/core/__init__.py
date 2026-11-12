"""Core mother folder: technical foundation shared by every other domain.

Sub-packages:
    * :mod:`warframe_lore.core.cli` -- the unified ``cephalon`` command line;
    * :mod:`warframe_lore.core.infra` -- local Docker/PostgreSQL bootstrap;
    * :mod:`warframe_lore.core.protocols` -- abstract contracts (SOLID / D)
      that high-level services depend on instead of concrete implementations.
"""
