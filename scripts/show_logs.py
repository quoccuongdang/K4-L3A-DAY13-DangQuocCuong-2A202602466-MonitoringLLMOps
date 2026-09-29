import json
from pathlib import Path

LOG_PATH = Path("data/logs.jsonl")

if not LOG_PATH.exists():
    print("Logs file not found.")
    exit(1)

records = [json.loads(line) for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

# Find latest response_sent record and its correlation_id
response_records = [r for r in records if r.get("event") == "response_sent"]
if not response_records:
    print("No response_sent events found.")
    exit(1)

cid = response_records[-1].get("correlation_id")
correlated = [r for r in records if r.get("correlation_id") == cid]

print(f"=== CORRELATED LOG PAIR (correlation_id: {cid}) ===\n")
for r in correlated:
    print(f"--- Event: {r.get('event')} ---")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print()
