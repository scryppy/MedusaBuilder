# string_obfuscator.py (Otimizado)

import base64
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from Cryptodome.Random import get_random_bytes

class SessionObfuscator:
    """
    Gerencia a ofuscação para uma única sessão de build, usando uma chave mestra.
    Isso é mais eficiente do que gerar uma chave para cada string.
    """
    def __init__(self):
        self.master_key = get_random_bytes(32)  # Chave AES-256 para esta sessão de build

    def get_master_key_b64(self) -> str:
        """Retorna a chave mestra da sessão, codificada em Base64."""
        return base64.b64encode(self.master_key).decode("utf-8")

    def obfuscate(self, original_string: str) -> tuple[str, str]:
        """
        Ofusca uma string usando a chave mestra da sessão.
        Retorna (iv_b64, encrypted_data_b64).
        """
        iv = get_random_bytes(AES.block_size)  # IV ainda é único por string para segurança
        cipher = AES.new(self.master_key, AES.MODE_CBC, iv)
        
        padded_data = pad(original_string.encode("utf-8"), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)

        iv_b64 = base64.b64encode(iv).decode("utf-8")
        encrypted_data_b64 = base64.b64encode(encrypted_data).decode("utf-8")

        return iv_b64, encrypted_data_b64

    @staticmethod
    def get_decrypt_function_code() -> str:
        """
        Retorna o código-fonte da função de descriptografia que será injetada no agente.
        A função agora espera a chave mestra como um argumento.
        """
        return """
import base64
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

_DECRYPT_CACHE = {}
_MASTER_KEY = None

def _init_decrypt(key_b64):
    global _MASTER_KEY
    if _MASTER_KEY is None:
        _MASTER_KEY = base64.b64decode(key_b64)

def rs(enc_str_b64: str, iv_b64: str) -> str:
    if enc_str_b64 in _DECRYPT_CACHE:
        return _DECRYPT_CACHE[enc_str_b64]
    try:
        iv = base64.b64decode(iv_b64)
        enc_str = base64.b64decode(enc_str_b64)
        cipher = AES.new(_MASTER_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(enc_str), AES.block_size)
        result = decrypted.decode("utf-8")
        _DECRYPT_CACHE[enc_str_b64] = result
        return result
    except Exception:
        return ""
"""
