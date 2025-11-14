
import os, json, hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .key_vault import load_key

def _aes_ctr(key: bytes, nonce16: bytes, data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce16))
    dec = cipher.decryptor()
    return dec.update(data) + dec.finalize()

def _aes_gcm_decrypt(key: bytes, nonce12: bytes, data: bytes) -> bytes:
    a = AESGCM(key)
    return a.decrypt(nonce12, data, None)

def decrypt_file(enc_path: str, out_path: str, key_id: str=None):
    ep = Path(enc_path)
    meta = ep.with_suffix(ep.suffix + ".meta.json")
    header = None
    with open(enc_path, "rb") as f:
        header = f.read(3)
        if not header:
            raise ValueError("Empty file")
        if header == b"CTR":
            nonce = f.read(16)
            ct = f.read()
            mode = "CTR"
        elif header == b"GCM":
            nonce = f.read(12)
            ct = f.read()
            mode = "GCM"
        elif header == b"CBC":
            iv = f.read(16)
            ct = f.read()
            mode = "CBC"
        else:
            raise ValueError("Unknown header")
    # load key
    if key_id is None:
        # try to find key id from meta
        if meta.exists():
            try:
                md = json.loads(meta.read_text())
                key_id = md.get("key_id")
            except Exception:
                key_id = None
    if not key_id:
        raise KeyError("key_id required or not found in .meta.json")
    key, stored_mode = load_key(key_id)
    if stored_mode and stored_mode.lower() != mode.lower():
        # allow modes difference but warn
        pass
    out_p = Path(out_path)
    tmp = out_p.with_suffix(out_p.suffix + ".tmp")
    if mode == "CTR":
        pt = _aes_ctr(key, nonce, ct)
        with open(tmp, "wb") as g:
            g.write(pt)
    elif mode == "GCM":
        pt = _aes_gcm_decrypt(key, nonce, ct)
        with open(tmp, "wb") as g:
            g.write(pt)
    elif mode == "CBC":
        # unpad
        from cryptography.hazmat.primitives import padding
        ch = Cipher(algorithms.AES(key), modes.CBC(iv))
        dec = ch.decryptor()
        padded = dec.update(ct) + dec.finalize()
        unpad = padding.PKCS7(128).unpadder()
        pt = unpad.update(padded) + unpad.finalize()
        with open(tmp, "wb") as g:
            g.write(pt)
    os.replace(str(tmp), str(out_p))
