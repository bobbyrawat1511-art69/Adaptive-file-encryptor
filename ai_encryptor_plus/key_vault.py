from __future__ import annotations
import os, sqlite3, secrets, time
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from .config import VAULT_DB, MASTER_ENV

# --- MODIFICATION ---
# Hum yahan se check HATATE hain.
# Check ko un functions ke andar move karenge jo key use karte hain.
#
# MASTER_SECRET = os.environ.get(MASTER_ENV)
# if not MASTER_SECRET:
#     raise RuntimeError(f"Set env {MASTER_ENV} to a strong secret (32+ chars).")
#
# --- END MODIFICATION ---

def _get_master_secret():
    """
    NAYA helper function jo runtime par secret nikalta hai.
    Store_key aur load_key se ye call hota hai.
    """
    secret = os.environ.get(MASTER_ENV)
    if not secret:
        # Ab error tab aata hai jab use hota hai, import time par nahi
        raise RuntimeError(
            f"{MASTER_ENV} set nahi hai. Server ne use se pehle set karna tha."
        )
    return secret

def _kdf(master: str, salt: bytes) -> bytes:
    # Master secret se encryption key derive karte hain
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    return kdf.derive(master.encode())

def _aes_cbc_encrypt(k: bytes, iv: bytes, pt: bytes) -> bytes:
    # Plaintext ko AES-CBC se encrypt karte hain
    cipher = Cipher(algorithms.AES(k), modes.CBC(iv))
    enc = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    return enc.update(padder.update(pt) + padder.finalize()) + enc.finalize()

def _aes_cbc_decrypt(k: bytes, iv: bytes, ct: bytes) -> bytes:
    # Ciphertext ko AES-CBC se decrypt karte hain
    cipher = Cipher(algorithms.AES(k), modes.CBC(iv))
    dec = cipher.decryptor()
    unpad = padding.PKCS7(128).unpadder()
    return unpad.update(dec.update(ct) + dec.finalize()) + unpad.finalize()

def _ensure_schema(conn: sqlite3.Connection):
    # Database table banate hain agar pehle se nahi hai
    conn.execute("""
    CREATE TABLE IF NOT EXISTS keys(
      id TEXT PRIMARY KEY,
      created_at INTEGER NOT NULL,
      salt BLOB NOT NULL,
      iv BLOB NOT NULL,
      wrapped_key BLOB NOT NULL,
      mode TEXT NOT NULL
    )""")
    conn.commit()

def init():
    # Database initialize karte hain
    with sqlite3.connect(VAULT_DB) as c:
        _ensure_schema(c)

def store_key(key_id: str, raw_key: bytes, mode: str) -> None:
    # Key ko vault mein store karte hain
    init()
    # --- MODIFICATION ---
    # Runtime par secret nikaalte hain, file ke top se nahi
    master_secret = _get_master_secret()
    # --- END MODIFICATION ---
    
    import secrets
    salt = secrets.token_bytes(16)
    wrap_k = _kdf(master_secret, salt)
    iv = secrets.token_bytes(16)
    wrapped = _aes_cbc_encrypt(wrap_k, iv, raw_key)
    with sqlite3.connect(VAULT_DB) as c:
        c.execute("REPLACE INTO keys(id,created_at,salt,iv,wrapped_key,mode) VALUES(?,?,?,?,?,?)",
                  (key_id, int(time.time()), salt, iv, wrapped, mode))
        c.commit()

def load_key(key_id: str):
    # --- MODIFICATION ---
    # Runtime par secret nikaalte hain, file ke top se nahi
    master_secret = _get_master_secret()
    # --- END MODIFICATION ---

    # Database se encrypted key nikaalte hain
    with sqlite3.connect(VAULT_DB) as c:
        row = c.execute("SELECT salt,iv,wrapped_key,mode FROM keys WHERE id=?",(key_id,)).fetchone()
        if not row:
            raise KeyError(f"key '{key_id}' nahi mila")
        salt, iv, wrapped, mode = row
    # Key ko decrypt karte hain aur return karte hain
    wrap_k = _kdf(master_secret, salt)
    raw = _aes_cbc_decrypt(wrap_k, iv, wrapped)
    return raw, mode