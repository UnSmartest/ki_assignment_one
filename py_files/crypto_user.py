#!/usr/bin/env python3
"""Encrypted storage for text inputs (registration sections + passwords).

Nothing is ever written to disk in plaintext. Every section is stored as
   data/<username>.<section>.aes.enc / .des.enc / .rc4.enc
Every encrypt/decrypt is written to crypto_log.txt and crypto_state.txt.

Commands (called from server.js):
  save_section <username> <section>      (section JSON on stdin)  -> encrypts
  decrypt_user <username> [AES|DES|RC4]                           -> decrypts + logs "Decryption"
  encrypt_password <username>            (password on stdin)      -> prints base64 ciphertext
  check_password <username> <b64enc>     (password on stdin)      -> prints OK / FAIL
"""
import sys
import json
import re
import time
import base64
import hmac
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from Crypto.Cipher import AES, ARC4, DES
from Crypto.Random import get_random_bytes

from crypto_logger import log_crypto, update_stats

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# Master keys (for assignment - normally would use env vars)
MASTER_KEY_AES = b"1234567890123456"  # 16 bytes
MASTER_KEY_DES = b"12345678"  # 8 bytes
MASTER_KEY_RC4 = b"masterkeyrc4secret"

SECTIONS = ("personal", "academic", "parent", "documents")
METHODS = ("AES", "DES", "RC4")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")  # usernames end up in file names


# ============================
# CIPHERS (AES/DES = CTR, RC4 = stream)
# ============================

def encrypt_aes_ctr(data: bytes, key: bytes) -> bytes:
    nonce = get_random_bytes(8)
    cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
    return nonce + cipher.encrypt(data)

def decrypt_aes_ctr(data: bytes, key: bytes) -> bytes:
    nonce, ciphertext = data[:8], data[8:]
    return AES.new(key, AES.MODE_CTR, nonce=nonce).decrypt(ciphertext)

def encrypt_des_ctr(data: bytes, key: bytes) -> bytes:
    nonce = get_random_bytes(4)
    cipher = DES.new(key, DES.MODE_CTR, nonce=nonce)
    return nonce + cipher.encrypt(data)

def decrypt_des_ctr(data: bytes, key: bytes) -> bytes:
    nonce, ciphertext = data[:4], data[4:]
    return DES.new(key, DES.MODE_CTR, nonce=nonce).decrypt(ciphertext)

def encrypt_rc4(data: bytes, key: bytes) -> bytes:
    return ARC4.new(key).encrypt(data)

def decrypt_rc4(data: bytes, key: bytes) -> bytes:
    return ARC4.new(key).decrypt(data)

ENCRYPT = {
    "AES": lambda d: encrypt_aes_ctr(d, MASTER_KEY_AES),
    "DES": lambda d: encrypt_des_ctr(d, MASTER_KEY_DES),
    "RC4": lambda d: encrypt_rc4(d, MASTER_KEY_RC4),
}
DECRYPT = {
    "AES": lambda d: decrypt_aes_ctr(d, MASTER_KEY_AES),
    "DES": lambda d: decrypt_des_ctr(d, MASTER_KEY_DES),
    "RC4": lambda d: decrypt_rc4(d, MASTER_KEY_RC4),
}


def check_username(username: str):
    if not USERNAME_RE.match(username or ""):
        raise ValueError("Invalid username")

def section_file(username: str, section: str, method: str) -> Path:
    return DATA_DIR / f"{username}.{section}.{method.lower()}.enc"


# ============================
# REGISTRATION SECTIONS
# ============================

def save_section(username: str, section: str, data: dict):
    """Encrypt ONE section with all three algorithms. No plaintext is stored."""
    check_username(username)
    if section not in SECTIONS:
        raise ValueError(f"Unknown section: {section}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data["saved"] = True
    data["savedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    raw = json.dumps(data).encode("utf-8")

    def encrypt_one(method):
        start = time.perf_counter()
        enc = ENCRYPT[method](raw)
        duration = time.perf_counter() - start
        section_file(username, section, method).write_bytes(enc)
        log_crypto("Encryption", method, f"{username}_{section}", len(raw), duration)

    with ThreadPoolExecutor(max_workers=3) as ex:
        for fut in as_completed([ex.submit(encrypt_one, m) for m in METHODS]):
            fut.result()
    update_stats()


def decrypt_user_data(username: str, method: str = "AES") -> dict:
    """Decrypt every saved section of this user. Each one is logged as 'Decryption'."""
    check_username(username)
    if method not in DECRYPT:
        raise ValueError(method)

    sections = {}
    for section in SECTIONS:
        f = section_file(username, section, method)
        if not f.exists():
            continue
        enc = f.read_bytes()
        start = time.perf_counter()
        raw = DECRYPT[method](enc)
        duration = time.perf_counter() - start
        log_crypto("Decryption", method, f"{username}_{section}", len(raw), duration)
        sections[section] = json.loads(raw.decode("utf-8"))

    if not sections:
        raise FileNotFoundError(f"No {method} encrypted data for {username}")
    update_stats()
    return {"sections": sections}


# ============================
# PASSWORDS (AES only)
# ============================

def encrypt_password(username: str, password: str) -> str:
    check_username(username)
    raw = password.encode("utf-8")
    start = time.perf_counter()
    enc = encrypt_aes_ctr(raw, MASTER_KEY_AES)
    duration = time.perf_counter() - start
    log_crypto("Encryption", "AES", f"{username}_password", len(raw), duration)
    update_stats()
    return base64.b64encode(enc).decode("ascii")


def check_password(username: str, enc_b64: str, password: str) -> bool:
    check_username(username)
    enc = base64.b64decode(enc_b64)
    start = time.perf_counter()
    raw = decrypt_aes_ctr(enc, MASTER_KEY_AES)
    duration = time.perf_counter() - start
    log_crypto("Decryption", "AES", f"{username}_password", len(raw), duration)
    update_stats()
    return hmac.compare_digest(raw, password.encode("utf-8"))


def read_stdin() -> str:
    # read raw bytes so non-ASCII text survives on Windows
    return sys.stdin.buffer.read().decode("utf-8")


def main():
    if len(sys.argv) < 2:
        return
    cmd = sys.argv[1]
    try:
        if cmd == "save_section" and len(sys.argv) >= 4:
            save_section(sys.argv[2], sys.argv[3], json.loads(read_stdin()))
            print("OK")
        elif cmd == "decrypt_user" and len(sys.argv) >= 3:
            method = sys.argv[3] if len(sys.argv) >= 4 else "AES"
            print(json.dumps(decrypt_user_data(sys.argv[2], method)))
        elif cmd == "encrypt_password" and len(sys.argv) >= 3:
            print(encrypt_password(sys.argv[2], read_stdin()))
        elif cmd == "check_password" and len(sys.argv) >= 4:
            print("OK" if check_password(sys.argv[2], sys.argv[3], read_stdin()) else "FAIL")
        else:
            print(json.dumps({"error": "bad command"}))
            sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
