"""Subcommand for RAG pipeline inspection and debugging.

Single responsibility: declare ``cephalon rag explain`` and bind it to
the explainer implementation in :mod:`warframe_lore.engram.rag.explain`.
"""

from __future__ import annotations

import argparse


def _cmd_rag_explain(args) -> int:
    import asyncio

    from warframe_lore.engram.rag.explain import explain_query
    return asyncio.run(explain_query(args.question, subject=args.subject))


def _cmd_rag(args) -> int:
    """Top-level ``cephalon rag`` handler: prints subcommand help."""
    print(
        "Usage: cephalon rag <action>\n\nActions:\n"
        "  explain   Trace a query step-by-step through the RAG pipeline."
    )
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    """Declare the RAG subcommands on ``sub``."""
    parser = sub.add_parser("rag", help="RAG pipeline inspection and diagnostics.")
    actions = parser.add_subparsers(dest="rag_action", metavar="ACTION")

    explain = actions.add_parser(
        "explain", help="Trace a query step-by-step through the RAG pipeline.")
    explain.add_argument("question", help="User question to trace.")
    explain.add_argument("--subject", default=None,
                         help="Optional targeted story subject.")
    explain.set_defaults(func=_cmd_rag_explain)
    parser.set_defaults(func=_cmd_rag)


__all__ = ["_cmd_rag", "_cmd_rag_explain", "register"]
