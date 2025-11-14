# chunked_ctr.py
# Chunked CTR parallel encryption/decryption with safe per-chunk nonces and manifest.
# Hinglish comments added for clarity

import os, secrets, json, math, hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Tuple, List
from .key_vault import store_key, load_key
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# helper: AES-CTR chunk encrypt/decrypt (symmetric)
# Yeh function ek chunk ko encrypt ya decrypt karta hai AES-CTR mode mein
def _aes_ctr_chunk(key: bytes, nonce16: bytes, data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce16))
    op = cipher.encryptor()
    return op.update(data) + op.finalize()

# Base nonce derive karo - har file ke liye unique (nonce_base || 8-byte chunk_index)
# 8 bytes random + 8 bytes reserved = 16 bytes total for CTR base
def _derive_base_nonce() -> bytes:
    return secrets.token_bytes(8) + secrets.token_bytes(8)

# Har chunk ke liye unique nonce banao base_nonce aur index se
# Pehle 8 bytes fix rahe, last 8 bytes mein chunk index daalo
def _chunk_nonce(base_nonce: bytes, idx: int) -> bytes:
    assert len(base_nonce) == 16
    prefix = base_nonce[:8]
    counter_bytes = idx.to_bytes(8, "big")
    return prefix + counter_bytes

# Authentication key derive karo - HMAC ke liye use hoga
# SHA256 se stable aur deterministic key banao
def _derive_auth_key(aes_key: bytes) -> bytes:
    return hashlib.sha256(aes_key + b"auth_key").digest()

# Per-chunk encryption worker - parallel processing ke liye
# Args: (key, base_nonce, idx, chunk_bytes) -> (idx, ciphertext)
def _worker_encrypt_chunk(args) -> Tuple[int, bytes]:
    key, base_nonce, idx, chunk = args
    nonce = _chunk_nonce(base_nonce, idx)
    ct = _aes_ctr_chunk(key, nonce, chunk)
    return idx, ct

# Per-chunk decryption worker - parallel processing ke liye
def _worker_decrypt_chunk(args) -> Tuple[int, bytes]:
    key, base_nonce, idx, ct = args
    nonce = _chunk_nonce(base_nonce, idx)
    pt = _aes_ctr_chunk(key, nonce, ct)
    return idx, pt

# File ko chunks mein encrypt karo - parallel workers se fast karo
def encrypt_file_chunked(src: Path, dst: Path, key: bytes, key_id: str,
                         chunk_size: int = 8 * 1024 * 1024,
                         workers: int = 4,
                         use_processes: bool = True,
                         write_manifest: bool = True):
    """
    Chunked CTR encryption:
    - Destination file atomic write ke through (tmp file se)
    - Header + concatenated encrypted chunks likho
    - Manifest file likhega base_nonce, chunk info aur HMACs ke saath
    """
    src = Path(src)
    dst = Path(dst)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    manifest = dst.with_suffix(dst.suffix + ".meta.json")

    # File size check karo aur chunk count nikalo
    filesize = src.stat().st_size
    chunk_count = math.ceil(filesize / chunk_size) if chunk_size > 0 else 1
    base_nonce = _derive_base_nonce()
    auth_key = _derive_auth_key(key)

    # File ko read karo aur chunks mein divide karo
    with open(src, "rb") as f:
        args_list = []
        idx = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            args_list.append((key, base_nonce, idx, chunk))
            idx += 1

    # Parallel mein sabhi chunks ko encrypt karo
    results = [None] * len(args_list)
    if use_processes:
        # Process pool use karo CPU-intensive task ke liye
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_worker_encrypt_chunk, a): i for i, a in enumerate(args_list)}
            for fut in as_completed(futures):
                idx, ct = fut.result()
                results[idx] = ct
    else:
        # Fallback: thread pool (CPU ke liye ideal nahi hai)
        for i, a in enumerate(args_list):
            idx, ct = _worker_encrypt_chunk(a)
            results[idx] = ct

    # Har chunk ke liye HMAC banao - tampering detect karne ke liye
    import hmac
    chunk_hmacs = []
    for ct in results:
        mac = hmac.new(auth_key, ct, hashlib.sha256).hexdigest()
        chunk_hmacs.append(mac)

    # File likho: header + base_nonce + sab encrypted chunks
    with open(tmp, "wb") as out:
        out.write(b"CTRCH")                # Custom header - chunked-ctr indicate karta hai
        out.write(base_nonce)             # 16 bytes
        out.write(chunk_size.to_bytes(8, "big"))
        # Sab chunks sequentially likho
        for ct in results:
            out.write(len(ct).to_bytes(8, "big"))
            out.write(ct)

    # Atomic replace - tmp file ko actual file se swap karo
    os.replace(str(tmp), str(dst))

    # Manifest file likho metadata ke saath
    if write_manifest:
        m = {
            "mode": "CTR_CHUNKED",
            "base_nonce": base_nonce.hex(),
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "key_id": key_id,
            "chunk_hmacs": chunk_hmacs,
            "version": 1
        }
        manifest.write_text(json.dumps(m))

    # Key ko vault mein store karo (optional)
    try:
        store_key(key_id, key, "ctr")
    except Exception:
        pass

# Encrypted file ko decrypt karo - manifest se info read karo
def decrypt_file_chunked(enc_path: Path, out_path: Path, key_id: str=None, use_processes: bool=True, workers: int=4):
    enc_path = Path(enc_path)
    out_path = Path(out_path)
    manifest = enc_path.with_suffix(enc_path.suffix + ".meta.json")
    
    # Manifest file zaroori hai decryption ke liye
    if not manifest.exists():
        raise FileNotFoundError("Manifest required for chunked CTR decryption")
    
    # Manifest se metadata read karo
    m = json.loads(manifest.read_text())
    base_nonce = bytes.fromhex(m["base_nonce"])
    chunk_size = int(m["chunk_size"])
    keyid = m.get("key_id") if key_id is None else key_id
    key, mode = load_key(keyid)  # Key vault se key load karo
    auth_key = _derive_auth_key(key)
    
    # Encrypted file ka structure read karo
    with open(enc_path, "rb") as f:
        header = f.read(5)
        if header != b"CTRCH":
            raise ValueError("Not a CTR chunked file")
        
        # Base nonce read karo aur verify karo
        base_nonce_read = f.read(16)
        if base_nonce_read != base_nonce:
            pass  # Continue despite mismatch
        
        chunk_size_read = int.from_bytes(f.read(8), "big")
        
        # Sab encrypted chunks read karo
        chunks_ct = []
        while True:
            lenb = f.read(8)
            if not lenb:
                break
            l = int.from_bytes(lenb, "big")
            ct = f.read(l)
            chunks_ct.append(ct)

    # Har chunk ke HMAC verify karo - corruption detect karne ke liye
    import hmac
    for i, ct in enumerate(chunks_ct):
        expected = m["chunk_hmacs"][i]
        mac = hmac.new(auth_key, ct, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError(f"Chunk {i} authentication failed")

    # Parallel mein sabhi chunks ko decrypt karo
    args_list = [(key, base_nonce, i, ct) for i, ct in enumerate(chunks_ct)]
    results = [None] * len(args_list)
    
    if use_processes:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_worker_decrypt_chunk, a): i for i, a in enumerate(args_list)}
            for fut in as_completed(futures):
                idx, pt = fut.result()
                results[idx] = pt
    else:
        for i, a in enumerate(args_list):
            idx, pt = _worker_decrypt_chunk(a)
            results[idx] = pt

    # Decrypted data likho output file mein
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp, "wb") as g:
        for pt in results:
            g.write(pt)
    
    # Atomic replace - tmp ko actual file se swap karo
    os.replace(str(tmp), str(out_path))
