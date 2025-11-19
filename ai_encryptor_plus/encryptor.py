import os, secrets, hashlib, json
from pathlib import Path
from typing import Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .key_vault import store_key

def gen_key() -> bytes:
    # 32 bytes = 256 bits AES key generate karo
    return secrets.token_bytes(32)  # AES-256

def _aes_ctr(key: bytes, nonce16: bytes, data: bytes) -> bytes:
    # CTR mode mein encryption karo
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce16))
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()

def _aes_gcm(key: bytes, nonce12: bytes, data: bytes) -> bytes:
    # GCM mode mein authenticated encryption karo
    a = AESGCM(key)
    return a.encrypt(nonce12, data, None)

# --- MODIFICATION ---
# Added 'master_secret' argument.
def encrypt_stream(path: str, out_path: str, mode: str, key_id: str, key: bytes, master_secret: str, chunk_size_bytes: int=1024*1024):
    # Temp file mein likho phir atomic replace karo
    out_p = Path(out_path)
    tmp = out_p.with_suffix(out_p.suffix + ".tmp")
    meta = out_p.with_suffix(out_p.suffix + ".meta.json")
    
    # key_id ko metadata mein store karo taaki decryptor use kar sake
    base_meta = {"key_id": key_id, "src": Path(path).name}
    
    with open(path, "rb") as f, open(tmp, "wb") as g:
        if mode.lower() == "ctr":
            # CTR mode: random nonce generate karo
            nonce = secrets.token_bytes(16)
            g.write(b"CTR"+nonce)  # header likho
            while True:
                chunk = f.read(chunk_size_bytes)
                if not chunk: break
                g.write(_aes_ctr(key, nonce, chunk))
            meta_data = {**base_meta, "mode":"CTR","nonce":nonce.hex(),"chunked":False}
        elif mode.lower() == "gcm":
            # GCM mode: puri file ek saath encrypt karo (tag ke liye)
            data = f.read()
            nonce = secrets.token_bytes(12)
            ct = _aes_gcm(key, nonce, data)
            g.write(b"GCM"+nonce+ct)
            meta_data = {**base_meta, "mode":"GCM","nonce":nonce.hex(),"chunked":False}
        else:
            # CBC mode: puri file padding ke saath encrypt karo
            from cryptography.hazmat.primitives import padding
            data = f.read()
            padder = padding.PKCS7(128).padder()
            padded = padder.update(data) + padder.finalize()
            iv = secrets.token_bytes(16)
            ch = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
            ct = ch.update(padded) + ch.finalize()
            g.write(b"CBC"+iv+ct)
            meta_data = {**base_meta, "mode":"CBC","iv":iv.hex(),"chunked":False}
    
    # File replace karo atomically
    os.replace(str(tmp), str(out_p))
    try:
        # Metadata JSON file mein save karo
        with open(meta, "w") as m:
            json.dump(meta_data, m, indent=2)
    except Exception:
        pass
    
    # --- MODIFICATION ---
    # Pass 'master_secret' to store_key.
    store_key(key_id, key, mode, master_secret)

def encrypt_file_whole_cbc(src: Path, dst: Path, key: bytes):
    # Puri file ko CBC mode mein encrypt karo
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    import secrets
    data = src.read_bytes()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    iv = secrets.token_bytes(16)
    ch = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ct = ch.update(padded) + ch.finalize()
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with open(tmp, "wb") as g:
        g.write(b"CBC"+iv+ct)
    # Atomically replace karo
    os.replace(str(tmp), str(dst))
