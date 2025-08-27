#!/usr/bin/env python3
"""Clean up generated files."""

import shutil
from pathlib import Path

def main():
    """Remove generated files and directories."""
    items_to_remove = [
        Path('./output'),
        Path('./create_pdf.py'),
        Path('./create_pdf_simple.py'),
        Path('./create_pdf_with_diagrams.py'),
        Path('./cleanup.py')
    ]
    
    for item in items_to_remove:
        if item.exists():
            if item.is_dir():
                shutil.rmtree(item)
                print(f"🗑️  Removed directory: {item}")
            else:
                item.unlink()
                print(f"🗑️  Removed file: {item}")
        else:
            print(f"⚠️  Not found: {item}")
    
    print("✅ Cleanup complete!")

if __name__ == '__main__':
    main()
