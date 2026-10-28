"""Atajo local. Desde esta carpeta: python soporte.py

Sin argumentos usa el pedido ord_10 de Ana. El texto que siga reemplaza ese mensaje.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from support_agent.sdk_runner import main

if __name__ == "__main__":
    main()
