-

#  **Adaptive file Encryption System**

A high-performance, multi-core, parallel file encryption platform with secure key management, auto-tuning, adaptive scheduling, and a clean browser-based UI. Built using Python, Flask, AES (GCM/CTR/CBC), multiprocessing, and envelope encryption.

This project efficiently encrypts/decrypts **single or multiple large files** using AES while fully utilizing all CPU cores — thanks to an intelligent “AI-Priority Scheduler” and chunked parallelism.

---

##  **Key Features**

###  **1. Secure AES Encryption (GCM/CTR/CBC)**

* **AES-GCM** → Best security + integrity + parallel performance
* **AES-CTR** → Fastest mode, ideal for parallel chunking
* **AES-CBC** → Legacy, serial, slower

The project supports secure metadata, nonces, IVs, and AEAD tags.

---

###  **2. Envelope Encryption (Production-Grade Security)**

Every file is encrypted with:

* **A fresh per-file Data Key**
* Data Key is wrapped (encrypted) using a **Master Key** derived from user password using **PBKDF2**
* Only wrapped keys are stored in `keyvault.db`

 Even if the database is stolen, attackers cannot decrypt files.

---

###  **3. adaptive Scheduler**

Predicts encryption difficulty using file:

* Size
* Entropy (compressibility)

Then schedules files from **fastest → slowest**, preventing the **straggler effect**:

> “One huge file never blocks the entire system.”

---

###  **4. Auto-Tuning Engine**

On startup, the system benchmarks:

* Ideal number of parallel workers
* Best chunk size

Example:

```
Auto-Tuned: 16 workers × 4MB chunks
```

Every machine gets optimal performance automatically.

---

###  **5. Chunked Parallel Encryption**

Large files are split into fixed-size chunks and encrypted in parallel using:

```
ProcessPoolExecutor (true multi-core parallelism)
```

This bypasses the Python GIL and achieves **maximum throughput**.

---

###  **6. Secure Decryption Workflow**

The decryption pipeline:

1. Unpacks encrypted ZIP
2. Derives Master Key
3. Unwraps Data Keys from DB
4. Verifies integrity (GCM tag)
5. Decrypts chunks in parallel
6. Places results in session-based folder
7. Serves files securely

---

###  **7. Web UI Dashboard**

Fully interactive UI:

* Multi-file upload
* Select mode (AES-GCM/CTR/CBC)
* Select scheduler (Naive/FIFO or AI-Priority)
* Visual logs
* Auto-tuner info display
* One-click download after encryption

---

###  **8. Clean REST API**

API endpoints:

* `/api/encrypt`
* `/api/decrypt`
* `/api/compare`
* `/api/settings`
* `/download/<session>/<file>`

---

##  **System Architecture**

```
Browser (UI)
     ↓  fetch()
Flask Server (REST API)
     ↓
File Profiling (entropy, size)
     ↓
AI Scheduler (priority queue)
     ↓
ProcessPoolExecutor (multi-core workers)
     ↓
Encrypt/Decrypt (stream or chunked)
     ↓
ZIP Packaging / Session Serving
     ↓
Browser Download
```

---

##  **Project Structure**

```
ai fe/
│
├── app.py                      # Flask server, routes, auto-tuner
├── keyvault.db                 # Stores wrapped keys (safe)
├── requirements.txt
│
└── ai_encryptor_plus/
    ├── encryptor.py            # Stream + chunked encryption
    ├── decryptor.py            # Stream + chunked decryption
    ├── cost_model.py           # Entropy + size prediction
    ├── scheduler_plus.py       # AI-Priority scheduling logic
    ├── key_vault.py            # PBKDF2, data-key wrap/unwrap
    ├── packager.py             # ZIP packaging + metadata
    │
    └── ui/
        ├── index.html
        ├── script.js
        └── style.css
```

---

##  **How It Works (Short Workflow)**

1. User uploads files + password
2. Server derives Master Key using PBKDF2
3. Files are **profiled** for size + entropy
4. AI Scheduler sorts files (small → large)
5. Auto-tuned settings decide chunk size/worker count
6. Each file gets:

   * New Data Key
   * Envelope-encrypted wrapped key
7. Small files → stream encryption
8. Large files → parallel chunked encryption
9. Everything packaged into a ZIP
10. Sent back to user from RAM (no file-lock issues)

---

##  **Decryption Flow**

1. User uploads encrypted ZIP
2. Metadata + wrapped keys extracted
3. Master Key derived
4. Data Keys unwrapped
5. Files decrypted (stream or chunked)
6. GCM tag verifies integrity
7. Files stored in session folder
8. Download available via secure endpoints

---

##  **Running the Application**

### Install dependencies:

```bash
pip install -r requirements.txt
```

### Run the server:

```bash
python app.py
```

### Open the UI:

```
http://127.0.0.1:5000
```

---

##  **Security Highlights**

* AES-GCM for authenticated encryption
* Fresh nonce for every encryption
* PBKDF2 with high iteration count
* Envelope encryption for safe key storage
* Atomic file writes using `os.replace()`
* No plaintext keys stored
* Temp directories securely cleaned

---

##  **Performance Features**

* True multi-core parallelism (multiprocessing)
* Chunked encryption for large files
* Auto-tuned worker and chunk size
* Reduction of straggler bottlenecks
* Zero-copy RAM-based download

---
##  **Why This Project Is Different**

Unlike basic AES scripts, this system is:

* Production-grade
* Fault-tolerant
* Multi-core optimized
* Secure with proper key management
* Usable by end-users via UI
* Architected with OS-level parallelism in mind
* Faster than standard FIFO scheduling (10–30% speedup)

---

Just tell me.
