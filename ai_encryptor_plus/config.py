import os

# VAULT_DB: vault database file ka path. Agar env var AI_ENC_VAULT nahi mili to "keyvault.db" use hoga.
VAULT_DB = os.environ.get("AI_ENC_VAULT", "keyvault.db")
# MASTER_ENV: master secret/key ke liye environment variable ka naam.
MASTER_ENV = "AI_ENC_MASTER"
# MODEL_PATH: cost model file ka path. Env AI_ENC_MODEL set kar sakte ho, warna default "cost_model.pkl".
MODEL_PATH = os.environ.get("AI_ENC_MODEL", "cost_model.pkl")
# CHECKPOINT_PATH: checkpoint file ka path. Default "out/checkpoint.json".
CHECKPOINT_PATH = os.environ.get("AI_ENC_CKP", "out/checkpoint.json")
# DEFAULT_CHUNK_MB: file ko chunks mein baantne ka size (MB). Env AI_ENC_CHUNK_MB se override ho sakta hai.
DEFAULT_CHUNK_MB = int(os.environ.get("AI_ENC_CHUNK_MB", "8"))
# ARCHIVE_NAME: encrypted outputs ka archive filename. Env AI_ENC_ARCHIVE se change kar sakte ho.
ARCHIVE_NAME = os.environ.get("AI_ENC_ARCHIVE", "encrypted_outputs.zip")
