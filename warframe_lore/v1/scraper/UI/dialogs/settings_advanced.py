"""Advanced discovery and graph fields for the settings dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QSpinBox

from ...settings.models import Settings


@dataclass(slots=True)
class AdvancedFields:
    """Widgets backing the optional discovery and graph configuration."""

    search_headers: QLineEdit
    git_token: QLineEdit
    wiki_apis: QLineEdit
    graph_enabled: QCheckBox
    graph_api_enabled: QCheckBox
    graph_api_host: QLineEdit
    graph_api_port: QSpinBox

    @classmethod
    def build(cls, form: QFormLayout, settings: Settings) -> AdvancedFields:
        """Create widgets and append them to the given form layout."""
        search_headers = QLineEdit(_format_pairs(settings.discovery_web_search_headers))
        search_headers.setPlaceholderText("Authorization: Bearer token, X-Key: value")
        form.addRow("Headers web search", search_headers)
        git_token = QLineEdit(settings.discovery_git_token)
        git_token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Token Git (optionnel)", git_token)
        wiki_apis = QLineEdit(", ".join(settings.discovery_wiki_api_urls))
        wiki_apis.setPlaceholderText("https://wiki.example/api.php")
        form.addRow("APIs wiki (optionnelles)", wiki_apis)
        graph_enabled = QCheckBox("Exporter le graphe des relations")
        graph_enabled.setChecked(settings.graph_enabled)
        form.addRow("", graph_enabled)
        graph_api_enabled = QCheckBox("API GraphQL locale (optionnelle)")
        graph_api_enabled.setChecked(settings.graph_api_enabled)
        form.addRow("", graph_api_enabled)
        graph_api_host = QLineEdit(settings.graph_api_host)
        form.addRow("Hôte API GraphQL", graph_api_host)
        graph_api_port = QSpinBox()
        graph_api_port.setRange(1, 65535)
        graph_api_port.setValue(settings.graph_api_port)
        form.addRow("Port API GraphQL", graph_api_port)
        return cls(
            search_headers,
            git_token,
            wiki_apis,
            graph_enabled,
            graph_api_enabled,
            graph_api_host,
            graph_api_port,
        )

    def values(self) -> dict[str, Any]:
        """Return keyword values ready for the Settings constructor."""
        return {
            "discovery_web_search_headers": _parse_pairs(self.search_headers.text()),
            "discovery_git_token": self.git_token.text().strip(),
            "discovery_wiki_api_urls": _split_values(self.wiki_apis.text()),
            "graph_enabled": self.graph_enabled.isChecked(),
            "graph_api_enabled": self.graph_api_enabled.isChecked(),
            "graph_api_host": self.graph_api_host.text().strip(),
            "graph_api_port": self.graph_api_port.value(),
        }


def _format_pairs(pairs: tuple[tuple[str, str], ...]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in pairs)


def _parse_pairs(text: str) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for entry in text.split(","):
        key, separator, value = entry.partition(":")
        if separator and key.strip():
            pairs.append((key.strip(), value.strip()))
    return tuple(pairs)


def _split_values(text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in text.split(",") if part.strip())
