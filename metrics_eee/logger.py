import json, hashlib, time
from typing import Dict, Any, Optional

def _hash_record(rec: Dict[str, Any], prev_hash: Optional[str] = None) -> str:
    h = hashlib.sha256()
    payload = json.dumps({"rec": rec, "prev": prev_hash}, sort_keys=True).encode()
    h.update(payload)
    return h.hexdigest()

def append_log(path: str, record: Dict[str, Any], prev_hash: Optional[str]) -> str:
    record['ts'] = int(time.time())
    record['prev_hash'] = prev_hash
    h = _hash_record(record, prev_hash)
    record['hash'] = h
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return h
