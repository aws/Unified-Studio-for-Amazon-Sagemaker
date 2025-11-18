#!/usr/bin/env python3
"""
Auto-fix common manifest issues in documentation files.
"""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

def fix_manifest_in_file(file_path):
    """Fix common manifest issues in a markdown file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix bundleName -> applicationName
    content = re.sub(
        r'bundleName:',
        'applicationName:',
        content
    )
    
    # Fix bundle: -> content: (but not in comments or text)
    content = re.sub(
        r'^bundle:\s*$',
        'content:',
        content,
        flags=re.MULTILINE
    )
    
    # Fix activation: workflows: -> content: workflows:
    content = re.sub(
        r'activation:\s*\n\s*workflows:',
        'content:\n  workflows:',
        content
    )
    
    if content != original:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all documentation files."""
    print("🔧 Fixing manifest issues in documentation...\n")
    
    fixed_count = 0
    for md_file in DOCS_DIR.rglob("*.md"):
        if fix_manifest_in_file(md_file):
            rel_path = md_file.relative_to(DOCS_DIR.parent)
            print(f"✅ Fixed: {rel_path}")
            fixed_count += 1
    
    print(f"\n📊 Fixed {fixed_count} file(s)")

if __name__ == "__main__":
    main()
