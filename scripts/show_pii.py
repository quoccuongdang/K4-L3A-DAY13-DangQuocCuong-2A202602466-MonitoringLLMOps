import json
from pathlib import Path

LOG_PATH = Path("data/logs.jsonl")

if not LOG_PATH.exists():
    print("Logs file not found.")
    exit(1)

print("=== 1. SAMPLE REDACTED LOG RECORDS IN data/logs.jsonl ===\n")
found_types = set()
for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
    if "REDACTED" in line:
        rec = json.loads(line)
        preview = rec.get("payload", {}).get("message_preview", "")
        cid = rec.get("correlation_id")
        
        pii_tag = None
        if "REDACTED_EMAIL" in preview and "EMAIL" not in found_types:
            pii_tag = "EMAIL"
        elif "REDACTED_PHONE_VN" in preview and "PHONE_VN" not in found_types:
            pii_tag = "PHONE_VN"
        elif "REDACTED_CREDIT_CARD" in preview and "CREDIT_CARD" not in found_types:
            pii_tag = "CREDIT_CARD"
            
        if pii_tag:
            found_types.add(pii_tag)
            print(f"[REDACTION TEST: {pii_tag}] (correlation_id: {cid})")
            print(json.dumps(rec, indent=2, ensure_ascii=False))
            print()
            
    if len(found_types) >= 3:
        break

print("=== 2. RUNNING LOG VALIDATOR ===")
import subprocess, sys
subprocess.run([sys.executable, "scripts/validate_logs.py"])
