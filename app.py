import os
import json
import time
import zipfile
import tempfile
import shutil
import io # Used for the in-memory file buffer
import uuid # Used for decryption session IDs
from flask import (
    Flask, request, send_from_directory, jsonify, 
    send_file, make_response, after_this_request
)
# Import flask-cors
from flask_cors import CORS
from pathlib import Path
from werkzeug.utils import secure_filename

# Import your existing, powerful Python logic
from ai_encryptor_plus.cli_plus import run_encrypt, run_decrypt
from ai_encryptor_plus.autotuner import tune_short
from ai_encryptor_plus.config import DEFAULT_CHUNK_MB

# --- Set defaults in the global scope ---
BEST_WORKERS = os.cpu_count() or 4
BEST_CHUNK_SIZE = DEFAULT_CHUNK_MB * 1024 * 1024

# --- A cache to hold paths to decrypted files ---
DECRYPTED_SESSIONS = {}

# Create the Flask web application
app = Flask(__name__, static_folder='ai_encryptor_plus/ui')

# --- Initialize CORS on your app ---
CORS(app)


# --- Page Routes ---

@app.route('/')
def serve_index():
    """Serves your index.html file"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serves any other files in your /ui folder (like CSS or JS)"""
    return send_from_directory(app.static_folder, filename)

@app.route('/api/settings')
def get_settings():
    """Provides the auto-detected settings to the UI."""
    return jsonify({
        "workers": BEST_WORKERS,
        "chunk_mb": BEST_CHUNK_SIZE // 1024 // 1024
    })

# --- Helper to read file and clean up ---

def _read_and_cleanup(file_path: Path, temp_dir: Path) -> io.BytesIO:
    """
    Helper to read a file into memory and immediately delete the temp folder.
    This fixes the Windows [WinError 32] file locking issue.
    """
    try:
        # Read the file into a memory buffer
        memory_buffer = io.BytesIO()
        with open(file_path, 'rb') as f:
            memory_buffer.write(f.read())
        memory_buffer.seek(0) # Rewind the buffer to the beginning
        
        print(f"--- File '{file_path.name}' read into memory. ---")
        return memory_buffer
    finally:
        # Now that the file is in memory, we can safely delete the temp dir
        print(f"--- Cleaning up temp directory: {temp_dir} ---")
        try:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temp dir: {e}")

# --- API Routes ---

@app.route('/api/encrypt', methods=['POST'])
def handle_encrypt():
    """
    This endpoint runs a SINGLE encryption job
    based on the selected policy.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        files = request.files.getlist('files')
        password = request.form.get('password')
        mode = request.form.get('mode', 'gcm')
        policy = request.form.get('policy', 'priority') 
        
        if not files or not password:
            return jsonify({"error": "Missing files or password"}), 400

        in_dir = temp_dir / "in"
        out_dir = temp_dir / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for f in files:
            f.save(in_dir / secure_filename(f.filename))
            
        os.environ['AI_ENC_MASTER'] = password
        
        print(f"--- Starting Single Run: Policy={policy} ---")
        
        time_elapsed, zip_path = run_encrypt(
            in_dir=str(in_dir), out_dir=str(out_dir),
            mode=mode, 
            workers=BEST_WORKERS, 
            # 'resume' is removed and hardcoded to False inside run_encrypt
            policy=policy, 
            use_processes=True, 
            chunk_size=BEST_CHUNK_SIZE
        )
        print(f"--- {policy} run complete in {time_elapsed:.4f}s ---")
        
        # Read file into memory and delete temp dir
        zip_buffer = _read_and_cleanup(Path(zip_path), temp_dir)

        response = make_response(send_file(
            zip_buffer, 
            as_attachment=True, 
            download_name=Path(zip_path).name
        ))
        response.headers['X-Time-Elapsed'] = f"{time_elapsed:.4f}"
        
        return response

    except Exception as e:
        print(f"Encrypt failed: {e}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return jsonify({"error": str(e)}), 500


@app.route('/api/compare', methods=['POST'])
def handle_compare():
    """
    This endpoint runs BOTH policies back-to-back for comparison.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        files = request.files.getlist('files')
        password = request.form.get('password')
        mode = request.form.get('mode', 'gcm')
        
        if not files or not password:
            return jsonify({"error": "Missing files or password"}), 400

        in_dir = temp_dir / "in"
        in_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            f.save(in_dir / secure_filename(f.filename))
            
        os.environ['AI_ENC_MASTER'] = password
        
        print(f"--- Starting Comparison: Running FIFO ---")
        out_dir_fifo = temp_dir / "out_fifo"
        time_fifo, zip_fifo_path = run_encrypt(
            in_dir=str(in_dir), out_dir=str(out_dir_fifo),
            mode=mode, workers=BEST_WORKERS, 
            policy='fifo', use_processes=True,
            chunk_size=BEST_CHUNK_SIZE
        )
        print(f"--- FIFO complete in {time_fifo:.4f}s ---")

        print(f"--- Starting Comparison: Running AI-Priority ---")
        out_dir_ai = temp_dir / "out_ai"
        time_ai, zip_ai_path = run_encrypt(
            in_dir=str(in_dir), out_dir=str(out_dir_ai),
            mode=mode, workers=BEST_WORKERS, 
            policy='priority', use_processes=True,
            chunk_size=BEST_CHUNK_SIZE
        )
        print(f"--- AI-Priority complete in {time_ai:.4f}s ---")

        # Read the AI zip into memory and delete the *entire* temp dir
        zip_buffer = _read_and_cleanup(Path(zip_ai_path), temp_dir)
        
        response = make_response(send_file(
            zip_buffer, 
            as_attachment=True, 
            download_name=Path(zip_ai_path).name
        ))
        response.headers['X-Time-FIFO'] = f"{time_fifo:.4f}"
        response.headers['X-Time-AI'] = f"{time_ai:.4f}"
        
        return response

    except Exception as e:
        print(f"Compare failed: {e}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir) 
        return jsonify({"error": str(e)}), 500


@app.route('/api/decrypt', methods=['POST'])
def handle_decrypt():
    """
    Decrypts files and returns a JSON list with a session ID.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        file = request.files.get('file')
        password = request.form.get('password')

        if not file or not password:
            return jsonify({"error": "Missing file or password"}), 400

        in_dir = temp_dir / "in"
        out_dir = temp_dir / "out" # This is where decrypted files will go
        zip_path = temp_dir / secure_filename(file.filename)
        
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        file.save(zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(in_dir)

        os.environ['AI_ENC_MASTER'] = password
        print(f"--- Starting backend decryption ---")

        run_decrypt(
            in_dir=str(in_dir), out_dir=str(out_dir),
            workers=BEST_WORKERS,
            use_processes=True
        )

        # 1. Scan the output directory for decrypted files
        decrypted_files = []
        for root, dirs, files in os.walk(out_dir):
            for f in files:
                relative_path = Path(root).relative_to(out_dir) / f
                decrypted_files.append(str(relative_path.as_posix()))

        # 2. Create a session ID and store the path
        session_id = str(uuid.uuid4())
        DECRYPTED_SESSIONS[session_id] = {
            "path": out_dir,
            "time": time.time()
        }
        
        print(f"--- Decryption complete. Found {len(decrypted_files)} files. Session: {session_id} ---")

        # 3. Return the JSON list of files
        return jsonify({
            "session_id": session_id,
            "files": decrypted_files
        })

    except Exception as e:
        print(f"Decryption failed: {e}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return jsonify({"error": str(e)}), 500

@app.route('/api/download_decrypted/<session_id>/<path:filename>')
def download_decrypted_file(session_id, filename):
    """
    This endpoint sends an individual decrypted file.
    """
    session = DECRYPTED_SESSIONS.get(session_id)
    if not session:
        return "Session not found or expired", 404
        
    base_path = Path(session["path"])
    safe_filename = Path(filename.replace("..", "")) # Basic sanitization
    file_path = (base_path / safe_filename).resolve()

    if not str(file_path).startswith(str(base_path.resolve())):
        print(f"--- FORBIDDEN: User tried to access file outside of session path ---")
        return "Forbidden", 403

    if not file_path.is_file():
        return "File not found", 404
        
    print(f"--- Sending file: {file_path} ---")
    
    return send_file(
        file_path, 
        as_attachment=True, 
        download_name=safe_filename.name
    )


def run_tuner():
    """Runs tuner and updates global variables."""
    global BEST_WORKERS, BEST_CHUNK_SIZE
    print("--- Running initial auto-tuner (this may take a few seconds)... ---")
    try:
        tuning_results = tune_short()
        BEST_WORKERS = tuning_results.get('best_workers', os.cpu_count() or 4)
        BEST_CHUNK_SIZE = tuning_results.get('best_chunk', DEFAULT_CHUNK_MB * 1024 * 1024)
        print(f"--- Auto-tuner complete: Using {BEST_WORKERS} workers and {BEST_CHUNK_SIZE // 1024 // 1024}MB chunks ---")
    except Exception as e:
        print(f"--- Auto-tuner failed ({e}), falling back to defaults ---")
        pass

if __name__ == '__main__':
    # Run tuner only when the *main* process starts
    run_tuner() 
    # Add exclude_patterns to stop reloads on temp/db file changes
    app.run(debug=True, port=5000, exclude_patterns=[
        "*.tmp", "*.db", "*.json", "*.json.tmp", "*.pkl", "*.db-journal"
    ])