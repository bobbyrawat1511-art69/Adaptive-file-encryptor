import os, zipfile
from pathlib import Path

def make_archive(out_dir: str, archive_name: str="encrypted_outputs.zip"):
    # out_dir ko Path object mein convert karo
    out_dir = Path(out_dir)
    # archive ka path banao
    arch_path = out_dir / archive_name
    # ZIP file create karo compression ke saath
    with zipfile.ZipFile(arch_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # out_dir ke andar sab files ko recursively iterate karo
        for p in out_dir.rglob("*"):
            # agar file hai aur archive file nahi hai to add karo
            if p.is_file() and p != arch_path:
                z.write(p, p.relative_to(out_dir))
    # archive ka path string format mein return karo
    return str(arch_path)
