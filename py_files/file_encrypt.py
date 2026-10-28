#!/usr/bin/env python3
import sys
import json
import os
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from Crypto.Cipher import AES, ARC4, DES
from Crypto.Random import get_random_bytes

from crypto_logger import log_crypto, update_stats

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
UNENCRYPTED_DIR = PROJECT_ROOT / "user_uploads"
ENCRYPTED_DIR = PROJECT_ROOT / "encrypted"

# Allowed extensions per requirements
ALLOWED = {
    "national_id": {".jpg", ".jpeg", ".png"},
    "transcript": {".pdf", ".docx", ".xls", ".xlsx"},
    "motivation": {".pdf", ".docx", ".xls", ".xlsx"},
    "video": {".mp4"},
    "all": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".mp4", ".txt", ".jpg", ".jpeg", ".png"}
}

MASTER_KEY_AES = b"1234567890123456"
MASTER_KEY_DES = b"12345678"
MASTER_KEY_RC4 = b"masterkeyrc4secret"

def encrypt_aes_ctr(data: bytes, key: bytes) -> bytes:
    nonce = get_random_bytes(8)
    cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
    return nonce + cipher.encrypt(data)

def encrypt_des_ctr(data: bytes, key: bytes) -> bytes:
    nonce = get_random_bytes(4)
    cipher = DES.new(key, DES.MODE_CTR, nonce=nonce)
    return nonce + cipher.encrypt(data)

def encrypt_rc4(data: bytes, key: bytes) -> bytes:
    cipher = ARC4.new(key)
    return cipher.encrypt(data)

def decrypt_aes_ctr(data: bytes, key: bytes) -> bytes:
    nonce, ciphertext = data[:8], data[8:]
    return AES.new(key, AES.MODE_CTR, nonce=nonce).decrypt(ciphertext)

def decrypt_file_for_user(username: str, filename: str):
    """Decrypt the AES copy of an uploaded file, log it as 'Decryption',
    and write the plaintext bytes to stdout (server.js pipes them to the browser)."""
    if Path(username).name != username or Path(filename).name != filename:
        print("BAD_NAME", file=sys.stderr)
        sys.exit(1)
    src = ENCRYPTED_DIR / "AES" / f"{username}_{filename}.aes.enc"
    if not src.exists():
        print(f"NOT_FOUND:{filename}", file=sys.stderr)
        sys.exit(1)

    enc = src.read_bytes()
    start = time.perf_counter()
    raw = decrypt_aes_ctr(enc, MASTER_KEY_AES)
    dur = time.perf_counter() - start

    log_crypto("Decryption", "AES", f"{username}:{filename}", len(raw), dur)
    update_stats()
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()

def encrypt_file_for_user(username: str, filename: str, field: str = "general"):
    UNENCRYPTED_DIR.mkdir(parents=True, exist_ok=True)
    (ENCRYPTED_DIR / "AES").mkdir(parents=True, exist_ok=True)
    (ENCRYPTED_DIR / "DES").mkdir(parents=True, exist_ok=True)
    (ENCRYPTED_DIR / "RC4").mkdir(parents=True, exist_ok=True)
    
    src = UNENCRYPTED_DIR / filename
    if not src.exists():
        print(f"NOT_FOUND:{filename}", file=sys.stderr)
        sys.exit(1)
    
    with open(src, 'rb') as f:
        data = f.read()
    
    methods = [
        ("AES", MASTER_KEY_AES, ENCRYPTED_DIR / "AES" / f"{username}_{filename}.aes.enc"),
        ("DES", MASTER_KEY_DES, ENCRYPTED_DIR / "DES" / f"{username}_{filename}.des.enc"),
        ("RC4", MASTER_KEY_RC4, ENCRYPTED_DIR / "RC4" / f"{username}_{filename}.rc4.enc"),
    ]
    
    def do_enc(mname, key, outpath):
        start = time.perf_counter()
        if mname == "AES":
            enc = encrypt_aes_ctr(data, key)
        elif mname == "DES":
            enc = encrypt_des_ctr(data, key)
        elif mname == "RC4":
            enc = encrypt_rc4(data, key)
        else:
            raise ValueError(mname)
        end = time.perf_counter()
        dur = end - start
        with open(outpath, 'wb') as f:
            f.write(enc)
        log_crypto("Encryption", mname, f"{username}:{filename}", len(data), dur)
        return mname, dur
    
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(do_enc, *m) for m in methods]
        for fut in as_completed(futs):
            fut.result()
    
    update_stats()
    # Optionally remove original after encryption for security
    try:
        os.remove(src)
    except Exception:
        pass
    print("OK")

def main():
    if len(sys.argv) < 4:
        return
    cmd = sys.argv[1]
    if cmd == "encrypt_file":
        username = sys.argv[2]
        filename = sys.argv[3]
        field = sys.argv[4] if len(sys.argv) > 4 else "general"
        encrypt_file_for_user(username, filename, field)
    elif cmd == "decrypt_file":
        decrypt_file_for_user(sys.argv[2], sys.argv[3])

if __name__ == "__main__":
    main()