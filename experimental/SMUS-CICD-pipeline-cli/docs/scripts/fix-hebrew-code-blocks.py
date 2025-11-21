#!/usr/bin/env python3
"""Fix code blocks in Hebrew README to be LTR."""

import re
from pathlib import Path

def fix_code_blocks_rtl(content: str) -> str:
    """Wrap code blocks in LTR divs for proper display in RTL context."""
    
    # Pattern to match code blocks (```...```)
    pattern = r'(```[\s\S]*?```)'
    
    def wrap_code_block(match):
        code_block = match.group(1)
        return f'<div dir="ltr">\n\n{code_block}\n\n</div>'
    
    # Replace all code blocks with LTR-wrapped versions
    fixed_content = re.sub(pattern, wrap_code_block, content)
    
    return fixed_content

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    he_readme = project_root / "docs" / "langs" / "he" / "README.md"
    
    print(f"Reading {he_readme}...")
    with open(he_readme, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Fixing code blocks to LTR...")
    fixed_content = fix_code_blocks_rtl(content)
    
    print(f"Saving updated file...")
    with open(he_readme, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("✅ Done! Code blocks are now LTR")

if __name__ == "__main__":
    main()
