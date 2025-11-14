import argparse, os, time, hashlib, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from typing import Tuple 

from .config import CHECKPOINT_PATH, DEFAULT_CHUNK_MB, ARCHIVE_NAME

from .encryptor import gen_key, encrypt_stream
from .key_vault import store_key, load_key
from .scheduler_plus import SchedulerPlus, Task 
from .packager import make_archive
from .decryptor import decrypt_file
from .chunked_ctr import encrypt_file_chunked

from .config import DEFAULT_CHUNK_MB

def sha256_file(p: Path) -> str:
    # Kya kar raha: File ka SHA256 hash calculate kar raha
    # Return: Hash ki hexadecimal string
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def run_encrypt(in_dir: str, out_dir: str, mode: str, workers: int=4, 
                # --- REMOVED 'resume' parameter ---
                use_processes: bool=False, 
                policy: str='priority', 
                chunk_size: int = (DEFAULT_CHUNK_MB * 1024 * 1024)
                ) -> Tuple[float, str]: # Return (time, zip_path)
    # Kya kar raha: Input directory ke saare files ko encrypt kar raha aur zip mein package kar raha
    # Return: (total_time_taken, archive_file_path)
    
    t_start = time.time() 
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Initializing AI scheduler...")
    scheduler = SchedulerPlus(max_workers=workers)
    # --- REMOVED: Checkpointer logic ---

    files = [p for p in in_dir.rglob("*") if p.is_file()]
    
    if policy == 'priority':
        print(f"Found {len(files)} files. AI (Priority) plan created.")
        t_plan_start = time.time()
        plan = scheduler.plan(files) 
        t_plan_end = time.time()
        print(f"AI planning took {t_plan_end - t_plan_start:.4f}s")
    else:
        print(f"Found {len(files)} files. FIFO plan created.")
        plan = [Task(prio=idx, path=p, size=p.stat().st_size, suffix=p.suffix.lower()) 
                for idx, p in enumerate(files)]
        
    if not plan:
        print("No files found to encrypt.")
        return 0.0, ""

    in_dir_hash = hashlib.sha256(str(in_dir).encode()).hexdigest()[:16]
    key_id = f"{in_dir_hash}-{mode}-{int(t_start)}" # Added timestamp to ensure unique key per run
    key = gen_key() 
    
    if mode.lower() == 'ctr':
        print(f"Using (hybrid) CTR mode. Processing {len(plan)} files...")
        
        for task in plan:
            p = task.path
            rel = p.relative_to(in_dir)
            outp = out_dir / rel.with_suffix(rel.suffix + ".enc")
            outp.parent.mkdir(parents=True, exist_ok=True)
            
            # --- REMOVED: resume check ---

            t0 = time.time()
            try:
                # --- HYBRID LOGIC ---
                if task.size < chunk_size:
                    # 1. Small File: Use simple, one-shot encrypt_stream
                    print(f"  [WORK-SIMPLE] {rel} (size: {task.size // 1024} KB)")
                    encrypt_stream(
                        path=str(p),
                        out_path=str(outp),
                        mode="ctr", # Force CTR mode
                        key_id=key_id,
                        key=key
                    )
                else:
                    # 2. Large File: Use powerful, parallel chunked encryptor
                    print(f"  [WORK-CHUNKED] {rel} (size: {task.size // 1024} KB)")
                    encrypt_file_chunked(
                        src=p, dst=outp, key=key, key_id=key_id,
                        chunk_size=chunk_size, 
                        workers=workers,
                        use_processes=use_processes
                    )
                
                # 3. Mark as done (same for both)
                elapsed = time.time() - t0
          
                scheduler.observe(p, elapsed)
                print(f"  [DONE] {rel} in {elapsed:.2f}s")
                
            except Exception as e:
                print(f"  [FAIL] {rel} - {e}")
            # --- END OF HYBRID LOGIC ---

    else:
        # --- GCM / CBC Logic ---
        print(f"Using (parallel-file) {mode.upper()} mode. Submitting {len(plan)} tasks...")
        exec_cls = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        
        with exec_cls(max_workers=workers) as ex:
            futures = {} 
            
            for task in plan:
                p = task.path
                rel = p.relative_to(in_dir)
                outp = out_dir / rel.with_suffix(rel.suffix + ".enc")
                outp.parent.mkdir(parents=True, exist_ok=True)


                
                t0 = time.time()
                f = ex.submit(encrypt_stream, str(p), str(outp), mode, key_id, key)
                futures[f] = (p, task, t0)

            for f in as_completed(futures):
                p, task, t0 = futures[f] 
                elapsed = time.time() - t0
                
                try:
                    f.result() 

                    scheduler.observe(p, elapsed)
                    print(f"  [DONE] {p.relative_to(in_dir)} in {elapsed:.2f}s")
                    
                except Exception as e:
                    print(f"  [FAIL] {p.relative_to(in_dir)} - {e}")

    print("Encryption run complete. Packaging outputs...")
    archive_name = f"encrypted_{policy}_{int(t_start)}.zip"
    arch_path = make_archive(out_dir, archive_name=archive_name)
    print(f"Packaged -> {arch_path}")

    t_end = time.time()
    total_elapsed = t_end - t_start 
    print(f"Total run time: {total_elapsed:.4f}s")
    
    return total_elapsed, arch_path


def run_decrypt(in_dir: str, out_dir: str, workers: int=4, use_processes: bool=False):
    # Kya kar raha: Encrypted files (.enc) ko decrypt kar raha
    # Return: Kuch nahi (None) - bas sidha decrypt kar raha
    
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    files = [p for p in in_dir.rglob("*.enc") if p.is_file()]
    if not files:
        payload_dir = in_dir / "payload"
        if payload_dir.exists():
            print("Found 'payload' directory, processing from there.")
            in_dir = payload_dir
            files = [p for p in in_dir.rglob("*.enc") if p.is_file()]
    
    exec_cls = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    with exec_cls(max_workers=workers) as ex:
        futures = []
        for p in files:
            rel = p.relative_to(in_dir)
            
            # Try to find the *original* name from the manifest
            outp_name = None
            # Check for chunked CTR meta file
            meta_path = p.with_suffix(p.suffix.replace(".enc", ".enc.meta.json"))
            if not meta_path.exists():
                # Check for simple GCM/CBC/CTR meta file
                meta_path = p.with_suffix(p.suffix + ".meta.json")

            if meta_path.exists():
                try:
                    meta_data = json.loads(meta_path.read_text())
                    # Check for 'src' key which is added by encrypt_stream
                    outp_name = meta_data.get("src") 
                except Exception:
                    pass # Will fall back to default name

            if not outp_name:
                # Default fallback name
                outp_name = ".".join(rel.name.split('.')[:-1]) if '.enc' in rel.name else rel.name + ".dec"

            outp = out_dir / rel.parent / outp_name
            outp.parent.mkdir(parents=True, exist_ok=True)

            key_id = None
            if meta_path.exists():
                try:
                    key_id = json.loads(meta_path.read_text()).get("key_id")
                except Exception:
                    key_id = None
            
            is_chunked = False
            if meta_path.exists():
                try:
                    is_chunked = json.loads(meta_path.read_text()).get("mode") == "CTR_CHUNKED"
                except Exception:
                    pass

            if is_chunked:
                from .chunked_ctr import decrypt_file_chunked
                print(f"  [DEC-CHUNK] {rel}")
                futures.append(ex.submit(decrypt_file_chunked, p, outp, key_id, use_processes, workers))
            else:
                # All other modes (GCM, CBC, simple CTR) are handled by decrypt_file
                print(f"  [DEC-SIMPLE] {rel}")
                futures.append(ex.submit(decrypt_file, str(p), str(outp), key_id))

        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"Decrypt error: {e}")

if __name__ == "__main__":
    # This main function is for running this file as a standalone CLI
    ap = argparse.ArgumentParser(description="AI Encryptor Plus (drop-in)")
    ap.add_argument("--action", choices=["encrypt","decrypt"], default="encrypt")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--mode", choices=["ctr","cbc","gcm"], default="gcm")
    ap.add_argument("--workers", type=int, default=4)

    ap.add_argument("--policy", choices=["priority", "fifo"], default="priority", help="File processing order")
    ap.add_argument("--use-processes", action="store_true", help="Use ProcessPoolExecutor for CPU-bound work")
    args = ap.parse_args()
    
    if args.action == "encrypt":
        run_encrypt(
            args.in_dir, args.out_dir, args.mode, 
            args.workers, 
            # resume is hardcoded to False since the CLI flag was removed
            False, 
            args.use_processes, args.policy
        )
    else:
        run_decrypt(args.in_dir, args.out_dir, args.workers, args.use_processes)