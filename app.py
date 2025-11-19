import os
import json
import time
import zipfile
import tempfile
import shutil
import uuid
import threading
from flask import (
    Flask, request, send_from_directory, jsonify, 
    send_file, make_response, after_this_request
)
from flask_cors import CORS
from pathlib import Path
from werkzeug.utils import secure_filename
from concurrent.futures import ProcessPoolExecutor

# Import your logic
from ai_encryptor_plus.cli_plus import run_encrypt, run_decrypt
from ai_encryptor_plus.autotuner import tune_short
from ai_encryptor_plus.config import DEFAULT_CHUNK_MB
from ai_encryptor_plus.scheduler_plus import SchedulerPlus

app = Flask(__name__, static_folder='ai_encryptor_plus/ui')
CORS(app)

# --- GLOBAL SYSTEM STATE (Lazy Loaded) ---
# We initialize these as None. They are spun up only on the first request.
GLOBAL_POOL = None
GLOBAL_SCHEDULER = None
_SYSTEM_LOCK = threading.Lock() # Lock to prevent race condition during tuning

# Defaults (will be updated by tuner)
BEST_WORKERS = 4
BEST_CHUNK_SIZE = DEFAULT_CHUNK_MB * 1024 * 1024

# Cache
DECRYPTED_SESSIONS = {}

# --- HELPER: LAZY INITIALIZATION ---
def ensure_system_ready():
    """
    Runs the auto-tuner and starts the process pool ONLY when needed.
    Uses a Lock to prevent concurrent tuning (solving the double-run issue).
    """
    global GLOBAL_POOL, GLOBAL_SCHEDULER, BEST_WORKERS, BEST_CHUNK_SIZE
    
    # 1. Fast Check (If initialized, exit quickly)
    if GLOBAL_POOL is not None:
        return

    # 2. Lock Critical Section (Only one thread can pass here)
    with _SYSTEM_LOCK:
        # 3. Double Check (Safety) - In case another thread finished while we waited
        if GLOBAL_POOL is not None:
            return

        print("--- 🐢 Lazy Loading: Waking up AI & Auto-Tuner... ---")
        try:
            # Run the benchmark now (first time)
            res = tune_short()
            BEST_WORKERS = res.get('best_workers', os.cpu_count() or 4)
            BEST_CHUNK_SIZE = res.get('best_chunk', DEFAULT_CHUNK_MB * 1024 * 1024)
            print(f"--- System Optimized: {BEST_WORKERS} Workers | {BEST_CHUNK_SIZE//1024//1024}MB Chunks ---")
        except Exception as e:
            print(f"--- Tuner skipped ({e}), using defaults ---")

        # Initialize the persistent OS resources
        GLOBAL_POOL = ProcessPoolExecutor(max_workers=BEST_WORKERS)
        GLOBAL_SCHEDULER = SchedulerPlus(max_workers=BEST_WORKERS)

# --- ROUTES ---

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/settings')
def get_settings():
    # User clicked a button or uploaded a file -> Initialize the system!
    ensure_system_ready()
    
    return jsonify({
        "workers": BEST_WORKERS,
        "chunk_mb": BEST_CHUNK_SIZE // 1024 // 1024
    })

@app.route('/api/encrypt', methods=['POST'])
def handle_encrypt():
    ensure_system_ready() # Ensure pool exists before processing
    
    temp_dir = Path(tempfile.mkdtemp())
    try:
        files = request.files.getlist('files')
        password = request.form.get('password')
        mode = request.form.get('mode', 'gcm')
        policy = request.form.get('policy', 'priority') 
        
        if not files or not password:
            return jsonify({"error": "Missing files/password"}), 400

        threshold_chunk = int(BEST_CHUNK_SIZE )

        in_dir = temp_dir / "in"
        out_dir = temp_dir / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for f in files:
            f.save(in_dir / secure_filename(f.filename))
            
        print(f"--- Processing ({policy}) ---")
        
        time_elapsed, zip_path_str = run_encrypt(
            in_dir=str(in_dir), out_dir=str(out_dir),
            mode=mode, master_secret=password,
            workers=BEST_WORKERS, policy=policy, 
            use_processes=True, chunk_size=threshold_chunk,
            scheduler=GLOBAL_SCHEDULER, executor=GLOBAL_POOL
        )
        
        zip_path = Path(zip_path_str)

        @after_this_request
        def cleanup(response):
            try: shutil.rmtree(temp_dir, ignore_errors=True)
            except: pass
            return response

        response = make_response(send_file(zip_path, as_attachment=True, download_name=zip_path.name))
        response.headers['X-Time-Elapsed'] = f"{time_elapsed:.4f}"
        return response

    except Exception as e:
        print(f"Error: {e}")
        if temp_dir.exists(): shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/compare', methods=['POST'])
def handle_compare():
    ensure_system_ready()
    
    temp_dir = Path(tempfile.mkdtemp())
    try:
        files = request.files.getlist('files')
        password = request.form.get('password')
        mode = request.form.get('mode', 'gcm')
        
        in_dir = temp_dir / "in"
        in_dir.mkdir(parents=True, exist_ok=True)
        for f in files: f.save(in_dir / secure_filename(f.filename))
            
        threshold_chunk = int(BEST_CHUNK_SIZE)

        print("--- Compare: FIFO ---")
        out_fifo = temp_dir / "out_fifo"
        t_fifo, _ = run_encrypt(
            str(in_dir), str(out_fifo), mode, password, BEST_WORKERS, 
            policy='fifo', use_processes=True, chunk_size=threshold_chunk,
            executor=GLOBAL_POOL
        )

        print("--- Compare: AI ---")
        out_ai = temp_dir / "out_ai"
        t_ai, z_ai = run_encrypt(
            str(in_dir), str(out_ai), mode, password, BEST_WORKERS, 
            policy='priority', use_processes=True, chunk_size=threshold_chunk,
            scheduler=GLOBAL_SCHEDULER, executor=GLOBAL_POOL
        )
        
        @after_this_request
        def cleanup(response):
            try: shutil.rmtree(temp_dir, ignore_errors=True)
            except: pass
            return response
            
        response = make_response(send_file(Path(z_ai), as_attachment=True, download_name=Path(z_ai).name))
        response.headers['X-Time-FIFO'] = f"{t_fifo:.4f}"
        response.headers['X-Time-AI'] = f"{t_ai:.4f}"
        return response

    except Exception as e:
        if temp_dir.exists(): shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/decrypt', methods=['POST'])
def handle_decrypt():
    ensure_system_ready()
    
    temp_dir = Path(tempfile.mkdtemp())
    try:
        file = request.files.get('file')
        password = request.form.get('password')

        in_dir = temp_dir / "in"
        out_dir = temp_dir / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = temp_dir / secure_filename(file.filename)
        file.save(zip_path)

        # Secure Extract
        with zipfile.ZipFile(zip_path, 'r') as z:
            for m in z.infolist():
                if m.is_dir(): continue
                target = (in_dir / m.filename).resolve()
                if str(target).startswith(str(in_dir.resolve())):
                    z.extract(m, in_dir)

        run_decrypt(
            str(in_dir), str(out_dir), password, BEST_WORKERS,
            use_processes=True, executor=GLOBAL_POOL
        )

        files = [str(Path(r).relative_to(out_dir)/f) for r,d,fs in os.walk(out_dir) for f in fs]
        sid = str(uuid.uuid4())
        DECRYPTED_SESSIONS[sid] = { "path": out_dir, "time": time.time() }
        
        return jsonify({ "session_id": sid, "files": files })

    except Exception as e:
        if temp_dir.exists(): shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/download_decrypted/<session_id>/<path:filename>')
def download_decrypted_file(session_id, filename):
    sess = DECRYPTED_SESSIONS.get(session_id)
    if not sess: return "Expired", 404
    safe_p = (Path(sess["path"]) / filename.replace("..", "")).resolve()
    if not safe_p.is_file(): return "Not found", 404
    return send_file(safe_p, as_attachment=True, download_name=safe_p.name)

if __name__ == '__main__':
    # We add exclude_patterns to stop the server from restarting 
    # when we write to keyvault.db or output folders, solving the previous stability issues.
    app.run(
        debug=True, 
        port=5000, 
        exclude_patterns=[
            "keyvault.db", 
            "*.db", 
            "*.db-journal", 
            "*.enc", 
            "*.json", 
            "*.tmp",
            "__pycache__",
            "*/site-packages/*",
            "*/Lib/*"
        ]
    )
