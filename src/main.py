from __future__ import annotations

import sys
from pathlib import Path

# Permitir ejecución directa: python src/main.py
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.app import Application
from src.config.config import Config, PROJECT_NAME, VERSION
from src.config.logger import LoggerManager


logger = LoggerManager.get_logger(__name__)


def show_banner() -> None:
    """
    Mostrar información inicial de la aplicación.
    """

    print()
    print("=" * 60)
    print(PROJECT_NAME)
    print(f"Versión {VERSION}")
    print("=" * 60)
    print()


def main() -> int:
    """
    Punto de entrada principal.
    """

    show_banner()

    try:

        config = Config()

        logger.info("Iniciando aplicación...")
        logger.info("Directorio raíz: %s", config.root_dir)
        logger.info("Input: %s", config.input_dir)
        logger.info("Output: %s", config.output_dir)
        logger.info("Resources: %s", config.resources_dir)
        logger.info("Logs: %s", config.log_dir)

        # ==========================
        # EJECUTAR LA APLICACIÓN
        # ==========================

        app = Application()
        app.run()

        print()
        print("=" * 60)
        print("Proceso finalizado correctamente.")
        print("=" * 60)

        return 0

    except Exception as error:

        logger.exception("Se produjo un error inesperado.")

        print()
        print("=" * 60)
        print("ERROR DURANTE LA EJECUCIÓN")
        print(error)
        print("=" * 60)

        return 1


if __name__ == "__main__":
    sys.exit(main())
