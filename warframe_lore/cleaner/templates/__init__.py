"""MediaWiki templates: signal, narrative rendering, and noise.

Three families grouped in this sub-package:
    * ``signal`` -- canon/non-canon signal (``{{Speculation}}``, ``{{Canon}}``);
    * ``render`` -- narrative template rendering (quote, spoiler, ...);
    * ``noise``  -- noise + first-pipe-argument fallback.

The English name ``NonCanon`` matches the real wiki templates
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
