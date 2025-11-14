# autotuner.py
# Chhota microbenchmark jo is machine ke liye chunk_size & worker_count pick karta hai.
import os, time, hashlib
from typing import Tuple, List
import multiprocessing
import tempfile
import math

def cpu_count():
    # CPU cores ki count nikalo
    try:
        return multiprocessing.cpu_count()
    except Exception:
        return 1

def _trial(chunk_size: int, workers: int, sample_mb: int = 16) -> float:
    # sample_mb size ka random buffer banao
    data = os.urandom(sample_mb * 1024 * 1024)
    # Memory copy + hashlib speed ko measure karo (encryption ka proxy)
    t0 = time.time()
    # Buffer ko chunk_size se divide karke parts banao
    parts = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    # Workers ke saath processing emulate karo
    import concurrent.futures
    def work(part):
        # CPU-bound crypto ko simulate karo sha256 se
        hashlib.sha256(part).digest()
        return True
    # ThreadPoolExecutor se parallel processing karo
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, parts))
    t1 = time.time()
    elapsed = t1 - t0
    # Throughput MB/s mein calculate karo
    throughput = len(data) / (1024*1024) / max(1e-6, elapsed)
    return throughput  # MB/s

def tune_short(trial_seconds: int = 3, candidate_chunks: List[int] = None) -> dict:
    # Default chunk sizes define karo agar nahi diye
    if candidate_chunks is None:
        candidate_chunks = [1*1024*1024, 4*1024*1024, 8*1024*1024, 16*1024*1024, 32*1024*1024]
    cpus = cpu_count()
    # Different worker counts try karo
    candidate_workers = list(range(1, min(2*cpus, 16)+1))
    results = {}
    # Har combination ko test karo
    for c in candidate_chunks:
        for w in [1, max(1, cpus//2), cpus, min(2*cpus, 16)]:
            try:
                perf = _trial(c, w)
                results[(c, w)] = perf
            except Exception:
                results[(c, w)] = 0.0
    # Sabse best combination pick karo
    best = max(results.items(), key=lambda kv: kv[1])
    best_chunk, best_workers = best[0]
    return {"best_chunk": best_chunk, "best_workers": best_workers, "all": results}
