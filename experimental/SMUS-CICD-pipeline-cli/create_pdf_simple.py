#!/usr/bin/env python3
"""
Create a single PDF from all markdown documents in the SMUS CI/CD pipeline CLI project.
Follows the linking structure starting from README.md.
Uses pandoc for PDF generation (simpler approach).
"""

import os
import re
from pathlib import Path
from typing import List, Set
import subprocess
import sys

def check_pandoc():
    """Check if pandoc is available."""
    try:
        result = subprocess.run(['pandoc', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Found pandoc: {result.stdout.split()[1]}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Pandoc not found. Please install pandoc:")
    print("  macOS: brew install pandoc")
    print("  Ubuntu: sudo apt-get install pandoc")
    print("  Windows: Download from https://pandoc.org/installing.html")
    return False

def find_markdown_links(content: str, base_path: Path) -> List[Path]:
    """Find all markdown links in content and resolve them to absolute paths."""
    links = []
    # Pattern to match markdown links: [text](path)
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    for match in re.finditer(link_pattern, content):
        link_text = match.group(1)
        link_path = match.group(2)
        
        # Skip external links (http/https)
        if link_path.startswith(('http://', 'https://')):
            continue
            
        # Skip anchor links
        if link_path.startswith('#'):
            continue
            
        # Resolve relative path
        if link_path.startswith('./'):
            link_path = link_path[2:]
        elif link_path.startswith('../'):
            # Handle relative paths going up directories
            resolved_path = base_path.parent / link_path
        else:
            resolved_path = base_path.parent / link_path
            
        # Normalize the path
        try:
            resolved_path = resolved_path.resolve()
            if resolved_path.exists() and resolved_path.suffix == '.md':
                links.append(resolved_path)
        except (OSError, ValueError):
            # Skip invalid paths
            continue
    
    return links

def clean_content_for_latex(content: str) -> str:
    """Clean content to be LaTeX-compatible."""
    # Replace common Unicode characters with LaTeX-friendly alternatives
    replacements = {
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARNING]',
        '🔍': '[SEARCH]',
        '📄': '[FILE]',
        '📕': '[PDF]',
        '🎉': '[SUCCESS]',
        '📊': '[STATS]',
        '🚀': '[DEPLOY]',
        '🔧': '[CONFIG]',
        '🆕': '[NEW]',
        '🎯': '[TARGET]',
        '📤': '[OUTPUT]',
        '🧪': '[TEST]',
        '🗑️': '[DELETE]',
        '📦': '[BUNDLE]',
        '→': '->',
        '←': '<-',
        '↑': '^',
        '↓': 'v',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '…': '...',
        '–': '-',
        '—': '--',
        # Box drawing characters
        '├': '|--',
        '└': '`--',
        '│': '|',
        '─': '-',
        '┌': ',--',
        '┐': '--.',
        '┘': "--'",
        '┴': '-+-',
        '┬': '-+-',
        '┤': '--|',
        '┼': '-+-',
        '╭': ',--',
        '╮': '--.',
        '╯': "--'",
        '╰': '`--',
        '╱': '/',
        '╲': '\\',
        '╳': 'X',
        # More emojis
        '📋': '[LIST]',
        '🌐': '[WEB]',
        '🔄': '[REFRESH]',
        '📁': '[FOLDER]',
        '🔗': '[LINK]',
        '⭐': '[STAR]',
        '💡': '[IDEA]',
        '🔒': '[LOCK]',
        '🔓': '[UNLOCK]',
        '🎨': '[DESIGN]',
        '🛠️': '[TOOLS]',
        '📈': '[CHART]',
        '📉': '[DECLINE]',
        '🎪': '[EVENT]',
        '🏗️': '[BUILD]',
        '🔥': '[HOT]',
        '💻': '[COMPUTER]',
        '📱': '[MOBILE]',
        '🖥️': '[DESKTOP]',
        '⚡': '[FAST]',
        '🌟': '[FEATURE]',
        '🎁': '[GIFT]',
        '🚨': '[ALERT]',
        '🔔': '[NOTIFICATION]',
        '🔕': '[SILENT]',
        '📢': '[ANNOUNCE]',
        '📣': '[MEGAPHONE]',
        '🎵': '[MUSIC]',
        '🎶': '[NOTES]',
        '🎤': '[MIC]',
        '🎧': '[HEADPHONES]',
        '📻': '[RADIO]',
        '📺': '[TV]',
        '📷': '[CAMERA]',
        '📸': '[PHOTO]',
        '🎬': '[MOVIE]',
        '🎭': '[THEATER]',
        '🎪': '[CIRCUS]',
        '🎨': '[ART]',
        '🖼️': '[PICTURE]',
        '🖌️': '[BRUSH]',
        '🖍️': '[CRAYON]',
        '📝': '[MEMO]',
        '📄': '[DOCUMENT]',
        '📃': '[PAGE]',
        '📑': '[BOOKMARK]',
        '📊': '[BAR_CHART]',
        '📈': '[TRENDING_UP]',
        '📉': '[TRENDING_DOWN]',
        '📇': '[CARD_INDEX]',
        '🗂️': '[CARD_FILE_BOX]',
        '🗃️': '[FILE_CABINET]',
        '🗄️': '[FILE_CABINET]',
        '🗑️': '[WASTEBASKET]',
        '🔒': '[LOCKED]',
        '🔓': '[UNLOCKED]',
        '🔏': '[LOCKED_WITH_PEN]',
        '🔐': '[LOCKED_WITH_KEY]',
        '🔑': '[KEY]',
        '🗝️': '[OLD_KEY]',
        '🔨': '[HAMMER]',
        '⛏️': '[PICK]',
        '⚒️': '[HAMMER_AND_PICK]',
        '🛠️': '[HAMMER_AND_WRENCH]',
        '🗡️': '[DAGGER]',
        '⚔️': '[CROSSED_SWORDS]',
        '🔫': '[PISTOL]',
        '🏹': '[BOW_AND_ARROW]',
        '🛡️': '[SHIELD]',
        '🔧': '[WRENCH]',
        '🔩': '[NUT_AND_BOLT]',
        '⚙️': '[GEAR]',
        '🗜️': '[CLAMP]',
        '⚖️': '[BALANCE_SCALE]',
        '🔗': '[LINK]',
        '⛓️': '[CHAINS]',
        '📎': '[PAPERCLIP]',
        '🖇️': '[LINKED_PAPERCLIPS]',
        '📐': '[TRIANGULAR_RULER]',
        '📏': '[STRAIGHT_RULER]',
        '📌': '[PUSHPIN]',
        '📍': '[ROUND_PUSHPIN]',
        '✂️': '[SCISSORS]',
        '🖊️': '[PEN]',
        '🖋️': '[FOUNTAIN_PEN]',
        '✒️': '[BLACK_NIB]',
        '🖌️': '[PAINTBRUSH]',
        '🖍️': '[CRAYON]',
        '📝': '[MEMO]',
        '✏️': '[PENCIL]',
        '🔍': '[MAGNIFYING_GLASS_LEFT]',
        '🔎': '[MAGNIFYING_GLASS_RIGHT]',
    }
    
    for unicode_char, replacement in replacements.items():
        content = content.replace(unicode_char, replacement)
    
    # Remove any remaining problematic Unicode characters by replacing with ASCII equivalents
    import unicodedata
    import re
    
    # Normalize Unicode characters
    content = unicodedata.normalize('NFKD', content)
    
    # Replace any remaining non-ASCII characters with their closest ASCII equivalent or remove them
    content = re.sub(r'[^\x00-\x7F]+', '', content)
    
    return content

def read_markdown_file(file_path: Path) -> str:
    """Read markdown file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return clean_content_for_latex(content)
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return ""

def collect_all_markdown_files(start_file: Path, visited: Set[Path] = None) -> List[Path]:
    """Recursively collect all markdown files following the link structure."""
    if visited is None:
        visited = set()
    
    if start_file.resolve() in visited:
        return []
    
    visited.add(start_file.resolve())
    files = [start_file]
    
    # Read the file and find linked markdown files
    content = read_markdown_file(start_file)
    linked_files = find_markdown_links(content, start_file)
    
    # Recursively process linked files
    for linked_file in linked_files:
        if linked_file.resolve() not in visited:
            files.extend(collect_all_markdown_files(linked_file, visited))
    
    return files

def create_combined_markdown(files: List[Path], output_path: Path):
    """Create a single markdown file from all collected files."""
    combined_content = []
    
    # Add title page
    combined_content.append("""% SMUS CI/CD Pipeline CLI Documentation
% Complete Documentation
% """ + subprocess.check_output(['date', '+%B %d, %Y'], text=True).strip() + """

\\newpage

""")
    
    for i, file_path in enumerate(files):
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path
        print(f"Processing: {rel_path}")
        content = read_markdown_file(file_path)
        
        if content:
            if i > 0:
                # Add page break before each new document (except first)
                combined_content.append("\\newpage\n")
            
            # Add section header with source file info
            if i == 0:
                # For README, keep original content but add source info
                try:
                    rel_path = file_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = file_path
                header = f"*Source: {rel_path}*\n\n"
                combined_content.append(header + content)
            else:
                # For other files, add clear section break
                section_title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
                try:
                    rel_path = file_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = file_path
                header = f"# {section_title}\n\n*Source: {rel_path}*\n\n"
                combined_content.append(header + content)
    
    # Write combined markdown
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(combined_content))
    
    print(f"✅ Combined markdown created: {output_path}")

def markdown_to_pdf_pandoc(markdown_path: Path, pdf_path: Path):
    """Convert markdown to PDF using pandoc."""
    # Add LaTeX to PATH
    import os
    env = os.environ.copy()
    latex_path = "/usr/local/texlive/2025basic/bin/universal-darwin"
    if latex_path not in env.get("PATH", ""):
        env["PATH"] = f"{latex_path}:{env.get('PATH', '')}"
    
    cmd = [
        'pandoc',
        str(markdown_path),
        '-o', str(pdf_path),
        '--pdf-engine=pdflatex',
        '--toc',
        '--toc-depth=3',
        '--number-sections',
        '-V', 'geometry:margin=1in',
        '-V', 'fontsize=11pt',
        '-V', 'documentclass=article',
        '-V', 'classoption=oneside',
        '--standalone'
    ]
    
    print("Converting to PDF using pandoc...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        print(f"✅ PDF created successfully: {pdf_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Pandoc failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def main():
    """Main function to create PDF from markdown files."""
    # Check for pandoc
    if not check_pandoc():
        return 1
    
    # Start from README.md
    start_file = Path('./README.md')
    if not start_file.exists():
        print("❌ Error: README.md not found in current directory")
        return 1
    
    print("🔍 Collecting markdown files following link structure...")
    
    # Collect all markdown files following links
    markdown_files = collect_all_markdown_files(start_file)
    
    # Also add any markdown files that might not be linked, but avoid duplicates
    project_root = Path('.')
    all_md_files = list(project_root.rglob('*.md'))
    
    # Create a set of already included files for deduplication (using resolved paths)
    included_files = set(f.resolve() for f in markdown_files)
    
    # Add files that weren't found through links
    for md_file in all_md_files:
        # Skip hidden directories and common exclusions
        if any(part.startswith('.') for part in md_file.parts):
            continue
        if 'node_modules' in md_file.parts or '__pycache__' in md_file.parts:
            continue
        if 'output' in md_file.parts:  # Skip output directory
            continue
        if md_file.resolve() not in included_files:
            markdown_files.append(md_file)
            included_files.add(md_file.resolve())
    
    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in markdown_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)
    
    markdown_files = unique_files
    
    print(f"📄 Found {len(markdown_files)} markdown files:")
    for f in markdown_files:
        try:
            rel_path = f.relative_to(Path.cwd())
        except ValueError:
            rel_path = f
        print(f"  - {rel_path}")
    
    # Create output directory
    output_dir = Path('./output')
    output_dir.mkdir(exist_ok=True)
    
    # Create combined markdown
    combined_md = output_dir / 'smus-cicd-documentation.md'
    create_combined_markdown(markdown_files, combined_md)
    
    # Convert to PDF
    pdf_output = output_dir / 'smus-cicd-documentation.pdf'
    success = markdown_to_pdf_pandoc(combined_md, pdf_output)
    
    if success:
        print(f"\n🎉 Documentation compiled successfully!")
        print(f"📄 Markdown: {combined_md}")
        print(f"📕 PDF: {pdf_output}")
        
        # Show file sizes
        md_size = combined_md.stat().st_size
        pdf_size = pdf_output.stat().st_size
        print(f"📊 Sizes: Markdown {md_size:,} bytes, PDF {pdf_size:,} bytes")
        
        return 0
    else:
        print(f"\n⚠️  Markdown file created but PDF conversion failed")
        print(f"📄 You can still use the markdown file: {combined_md}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
