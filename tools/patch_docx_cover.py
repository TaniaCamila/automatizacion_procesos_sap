from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def patch(path: Path, *, design: bool) -> None:
    replacements = {
        "Propuesta de Proyecto       y Especificación de Requisitos de Software": (
            "Documento de Diseño de Software" if design else "Especificación de Requisitos de Software"
        ),
        "Proyecto: [Insertar Nombre de Proyecto]": "Proyecto: Operations Analytics Automatización de Procesos SAP",
        "Revisión: [01]": "Revisión: [1.0]",
        "[Seleccionar fecha]": "1 de octubre de 2026",
    }
    temp = path.with_suffix(".cover-patch.tmp")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temp, "w") as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "word/document.xml":
                root = etree.fromstring(payload)
                for paragraph in root.xpath(".//w:p", namespaces=NS):
                    nodes = paragraph.xpath(".//w:t", namespaces=NS)
                    if not nodes:
                        continue
                    combined = "".join(node.text or "" for node in nodes)
                    revised = combined
                    for old, new in replacements.items():
                        revised = revised.replace(old, new)
                    if revised != combined:
                        nodes[0].text = revised
                        for node in nodes[1:]:
                            node.text = ""
                payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif info.filename == "word/settings.xml":
                root = etree.fromstring(payload)
                update = root.find(f"{{{W_NS}}}updateFields")
                if update is None:
                    update = etree.SubElement(root, f"{{{W_NS}}}updateFields")
                update.set(f"{{{W_NS}}}val", "true")
                payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(info, payload)
    os.replace(temp, path)


if __name__ == "__main__":
    patch(Path(sys.argv[1]), design="--design" in sys.argv[2:])
