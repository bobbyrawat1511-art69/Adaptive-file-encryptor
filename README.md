AI-Powered Encryptor Dashboard:

This is a demo app that provides a secure, high-performance file encryption service. It features an "AI-Priority" scheduler that intelligently analyzes files and optimizes the encryption order to maximize throughput, which you can benchmark directly against a standard "Naive-FIFO" (First-In, First-Out) method.

The application automatically tunes itself on startup to find the best performance settings for the machine it's running on, creating a smart, hybrid encryption strategy that uses the best tool for every file.


AI-Powered Scheduler: Automatically uses a cost model to predict the encryption time for each file, then processes the fastest files first to keep all CPU cores busy and minimize total runtime.

Performance Comparison: A dedicated "Compare" tab runs encryption using both the Naive-FIFO and AI-Priority policies, displaying a clear statistical summary of which was faster and by how much.

Auto-Tuning: On server startup, the application runs a micro-benchmark (from autotuner.py) to find the optimal number of worker processes and the best file chunk size for the host machine.

Hybrid Encryption (for CTR Mode): Intelligently uses the auto-tuned settings to decide how to encrypt:

Small Files: Uses a simple, low-overhead, single-shot encryption.

Large Files: Automatically uses the powerful, parallel encrypt_file_chunked logic.

Secure Key Vault: Uses a master password (provided in the UI) to encrypt and store all file keys in a secure SQLite database (keyvault.db).

Interactive Decryption: The "Decrypt" tab allows you to upload an encrypted .zip package. The server decrypts it and provides individual download links for each original file.

💻 Tech Stack
Backend: Python, Flask, flask-cors

Encryption: cryptography library

Database: SQLite (for the key vault)

Frontend: HTML, CSS, JavaScript (ES6+)

""Project Structure""

AI FE/
│
├── app.py                  # The main Flask web server
├── keyvault.db             # The SQLite database for storing encryption keys
├── requirements.txt        # Python libraries needed for the project
│
└── ai_encryptor_plus/      # The core Python package
    │
    ├── ui/                 # All frontend files
    │   ├── index.html      # The main HTML structure
    │   ├── style.css       # The CSS for the dashboard
    │   └── script.js       # The JavaScript for API calls and UI logic
    │
    ├── adaptive_predictor.py # Base-level prediction logic
    ├── autotuner.py        # Runs benchmarks to find optimal settings
    ├── chunked_ctr.py      # Handles parallel encryption for large files
    ├── cli_plus.py         # The core "brain" that orchestrates all backend tasks
    ├── config.py           # Stores configuration (db paths, chunk sizes)
    ├── cost_model.py       # Predicts encryption time for the AI scheduler
    ├── decryptor.py        # Handles file decryption logic
    ├── encryptor.py        # Handles simple/GCM/CBC file encryption logic
    ├── key_vault.py        # Manages secure storage/retrieval of keys
    ├── packager.py         # Creates the final .zip archive
    └── scheduler_plus.py   # The "AI" scheduler that prioritizes files