from __future__ import annotations

from typing import Mapping


"""
Constantes de moneda y compatibilidad (BUSINESS-02).

Los conceptos administrables viven en CONCEPTOS_ADMIN.xlsx
y se cargan vía concept_classifier.load().
"""

CURRENCY_USD = "USD"
CURRENCY_NO_USD = "NO_USD"

# Compatibilidad: ya no se mantienen conceptos hardcodeados.
CONCEPT_GROUPS: Mapping[str, tuple[str, ...]] = {}


def all_concepts() -> tuple[str, ...]:
    """Delegar al catálogo admin cargado en el clasificador."""

    from ..services import concept_classifier

    concept_classifier.ensure_loaded()
    return concept_classifier.all_standard_concepts()


def concept_to_group() -> dict[str, str]:
    """Delegar al catálogo admin cargado en el clasificador."""

    from ..services import concept_classifier

    concept_classifier.ensure_loaded()
    return concept_classifier.standard_to_group()


__all__ = (
    "CONCEPT_GROUPS",
    "CURRENCY_USD",
    "CURRENCY_NO_USD",
    "all_concepts",
    "concept_to_group",
)
