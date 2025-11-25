#!/usr/bin/env python3
"""
Validate that all documentation files have back links to main README.
"""

import sys
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

def has_backlink(content):
    """Check if file has a back link."""
    return "Back to Main README" in content or "← [Back to" in content

def main():
    """Check all documentation files for back links."""
    print("🔍 Checking documentation files for back links...\n")
    
    missing = []
    
    for md_file in DOCS_DIR.rglob("*.md"):
        with open(md_file, 'r') as f:
            content = f.read()
        
        if not has_backlink(content):
            rel_path = md_file.relative_to(DOCS_DIR.parent)
            missing.append(str(rel_path))
    
    if missing:
        print("❌ Missing back links in:")
        for path in missing:
            print(f"   {path}")
        print(f"\n💡 Run: python tests/scripts/add_doc_backlinks.py")
        return 1
    else:
        print("✅ All documentation files have back links!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
