"""Templates MediaWiki : signal, rendu narratif et bruit.

Trois familles regroupées dans ce sous-paquet :
    * ``signal`` — signal canon/non-canon (``{{Speculation}}``, ``{{Canon}}``) ;
    * ``render`` — rendu des templates narratifs (quote, spoiler, ...) ;
    * ``noise``  — bruit + fallback premier argument pipe.

Le nom anglais ``NonCanon`` colle aux templates réels du wiki
(``{{Speculation}}``, ``{{Conjecture}}``).
"""

from __future__ import annotations

from .noise import (
    is_noise_template,
    is_pure_noise,
    strip_templates_to_text,
)
from .render import (
    render_canon_template,
    render_non_canon_template,
    render_quote_template,
    render_spoiler_template,
)
from .signal import (
    must_flag_canon,
    must_flag_non_canon,
)

__all__ = [
    "must_flag_non_canon",
    "must_flag_canon",
    "render_canon_template",
    "render_non_canon_template",
    "render_quote_template",
    "render_spoiler_template",
    "is_noise_template",
    "is_pure_noise",
    "strip_templates_to_text",
]