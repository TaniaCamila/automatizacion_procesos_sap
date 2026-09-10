from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Type, TypeVar


T = TypeVar("T", bound="RegistroFBL1N")


@dataclass(slots=True)
class RegistroFBL1N:
    """Representa un registro extraído del Excel FBL1N.

    Atributos:
        sociedad: Código o identificador de la sociedad.
        moneda: Código de la moneda.
        importe: Importe numérico (float).
        fecha_compensacion: Fecha de compensación o ``None``.
        texto_cabecera: Texto descriptivo del encabezado.
    """

    sociedad: str
    moneda: str
    importe: float
    fecha_compensacion: datetime | None
    texto_cabecera: str

    def to_dict(self) -> Dict[str, Any]:
        """Convertir el registro a un diccionario serializable.

        La fecha de compensación se representa en formato ISO 8601
        si no es ``None``.
        """
        return {
            "sociedad": self.sociedad,
            "moneda": self.moneda,
            "importe": self.importe,
            "fecha_compensacion": (
                self.fecha_compensacion.isoformat()
                if self.fecha_compensacion is not None
                else None
            ),
            "texto_cabecera": self.texto_cabecera,
        }

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Construir un `RegistroFBL1N` a partir de un diccionario.

        Acepta `fecha_compensacion` como `datetime`, cadena ISO o `None`.
        """
        fecha = data.get("fecha_compensacion")
        if isinstance(fecha, str):
            fecha_val: datetime | None = datetime.fromisoformat(fecha)
        else:
            fecha_val = fecha  # type: ignore[assignment]

        return cls(
            sociedad=str(data.get("sociedad", "")),
            moneda=str(data.get("moneda", "")),
            importe=float(data.get("importe", 0.0)),
            fecha_compensacion=fecha_val,
            texto_cabecera=str(data.get("texto_cabecera", "")),
        )


__all__ = ("RegistroFBL1N",)
