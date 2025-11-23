#!/usr/bin/env python3
"""Verify notebook integrity - temporary debugging script."""
import json
import hashlib
import sys

def verify_notebook(path, label):
    """Check notebook structure and report."""
    try:
        with open(path, 'rb') as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        with open(path) as f:
            nb = json.load(f)
            cell0_len = len(nb['cells'][0]['source']) if nb.get('cells') else 0
            first_line = nb['cells'][0]['source'][0][:60] if cell0_len > 0 else 'N/A'
        
        print(f"✓ {label}")
        print(f"  Checksum: {checksum}")
        print(f"  Cell 0 length: {cell0_len}")
        print(f"  First line: {first_line}")
        
        if cell0_len == 1:
            print(f"  ❌ CORRUPTED: Cell 0 has only 1 element (should be ~11)")
            return False
        elif cell0_len >= 10:
            print(f"  ✅ OK: Cell 0 has {cell0_len} elements")
            return True
        else:
            print(f"  ⚠️  WARNING: Cell 0 has {cell0_len} elements (expected ~11)")
            return False
    except Exception as e:
        print(f"❌ {label}: ERROR - {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: verify_notebook.py <path> <label>")
        sys.exit(1)
    
    path = sys.argv[1]
    label = sys.argv[2]
    success = verify_notebook(path, label)
    sys.exit(0 if success else 1)
