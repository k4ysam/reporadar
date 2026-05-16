"""Publishing / Export service.

Manual export is the default mode — `manual_export_adapter` writes a JSON
package next to the rendered image so the operator can copy/paste and post
manually. Future API adapters (LinkedIn, Instagram Graph) go in `adapters/`.
"""
from src.publishing.service import publish_packages

__all__ = ["publish_packages"]
