#!/usr/bin/env python3
"""Shared logging + statistics for all encryption/decryption operations.

Writes to:
  crypto_log.txt    - one line per operation
  crypto_state.txt  - aggregated statistics (rebuilt from crypto_log.txt)
"""
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "crypto_log.txt"
STAT_FILE = PROJECT_ROOT / "crypto_state.txt"

ALGO_TYPES = ("Encryption", "Decryption")

# Matches:  Type: Encryption | Method: AES | File: x | Size: 12 bytes | Time: 0.001234s
LOG_PATTERN = re.compile(
    r"Type: (?P<type>\w+) \| Method: (?P<method>\w+) \| File: .* "
    r"\| Size: \d+ bytes \| Time: (?P<time>[\d.]+)s"
)


def log_crypto(algorithm_type: str, method: str, filename: str,
               file_size: int, duration: float):
    """Append one line to crypto_log.txt. duration is in SECONDS."""
    if algorithm_type not in ALGO_TYPES:
        raise ValueError(f"algorithm_type must be one of {ALGO_TYPES}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (f"[{timestamp}] Type: {algorithm_type} | Method: {method} | "
             f"File: {filename} | Size: {file_size} bytes | "
             f"Time: {duration:.6f}s\n")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


def update_stats():
    """Rebuild crypto_state.txt from crypto_log.txt."""
    times = {}  # (algorithm_type, method) -> [seconds, ...]
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                m = LOG_PATTERN.search(line)
                if m:
                    key = (m.group("type"), m.group("method"))
                    times.setdefault(key, []).append(float(m.group("time")))

    with open(STAT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("CRYPTO STATISTICS (Average Speed & Performance)\n")
        f.write("Mode: CTR (AES/DES) | RC4 (Stream Cipher)\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if not times:
            f.write("No encryption/decryption runs recorded yet.\n")
        else:
            for algo_type in ALGO_TYPES:
                for method in sorted(k[1] for k in times if k[0] == algo_type):
                    t = times[(algo_type, method)]
                    avg = sum(t) / len(t)
                    f.write(f"Algorithm Type: {algo_type}\n")
                    f.write(f"Method: {method}\n")
                    f.write(f"  Number of operations: {len(t)}\n")
                    f.write(f"  Total time: {sum(t):.6f}s\n")
                    f.write(f"  Average time: {avg:.6f}s ({avg * 1000:.3f}ms)\n")
                    f.write(f"  Fastest: {min(t):.6f}s\n")
                    f.write(f"  Slowest: {max(t):.6f}s\n\n")
        f.write("=" * 60 + "\n")