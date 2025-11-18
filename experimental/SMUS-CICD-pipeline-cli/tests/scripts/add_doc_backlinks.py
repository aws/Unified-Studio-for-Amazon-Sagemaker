#!/usr/bin/env python3
"""
Add back links to main README in all documentation files.
"""

from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

def has_backlink(content):
    """Check if file already has a back link."""
    return "Back to Main README" in content or "← [Back to" in content

def add_backlink(file_path):
    """Add back link to a documentation file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    if has_backlink(content):
        return False
    
    # Determine relative path to main README
    rel_depth = len(file_path.relative_to(DOCS_DIR).parts) - 1
    readme_path = "../" * (rel_depth + 1) + "README.md"
    
    # Find first heading
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# '):
            # Insert back link after the heading
            lines.insert(i + 1, '')
            lines.insert(i + 2, f'← [Back to Main README]({readme_path})')
            lines.insert(i + 3, '')
            break
    
    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))
    
    return True

def main():
    """Add back links to all documentation files."""
    print("🔗 Adding back links to documentation files...\n")
    
    added_count = 0
    
    # Process all markdown files
    for md_file in DOCS_DIR.rglob("*.md"):
        if add_backlink(md_file):
            rel_path = md_file.relative_to(DOCS_DIR.parent)
            print(f"✅ Added: {rel_path}")
            added_count += 1
    
    print(f"\n📊 Added back links to {added_count} file(s)")

if __name__ == "__main__":
    main()
