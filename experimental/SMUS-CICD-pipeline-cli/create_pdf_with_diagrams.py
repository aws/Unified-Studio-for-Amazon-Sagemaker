#!/usr/bin/env python3
"""
Create a single PDF from all markdown documents with rendered diagrams.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Set
import tempfile
import hashlib

def check_dependencies():
    """Check for required dependencies."""
    missing = []
    
    # Check pandoc
    try:
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        print("✅ Found pandoc")
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("pandoc")
    
    # Check mermaid-cli
    try:
        subprocess.run(['mmdc', '--version'], capture_output=True, check=True)
        print("✅ Found mermaid-cli")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  mermaid-cli not found, installing...")
        try:
            subprocess.run(['npm', 'install', '-g', '@mermaid-js/mermaid-cli'], check=True)
            print("✅ Installed mermaid-cli")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("mermaid-cli (npm install -g @mermaid-js/mermaid-cli)")
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        return False
    
    return True

def extract_and_render_diagrams(content: str, output_dir: Path) -> str:
    """Extract mermaid diagrams and render them as images."""
    diagram_pattern = r'```mermaid\n(.*?)\n```'
    diagrams = re.findall(diagram_pattern, content, re.DOTALL)
    
    if not diagrams:
        return content
    
    print(f"Found {len(diagrams)} mermaid diagrams to render...")
    
    for i, diagram_code in enumerate(diagrams):
        # Create unique filename based on diagram content
        diagram_hash = hashlib.md5(diagram_code.encode()).hexdigest()[:8]
        diagram_file = output_dir / f"diagram_{i}_{diagram_hash}"
        mermaid_file = diagram_file.with_suffix('.mmd')
        png_file = diagram_file.with_suffix('.png')
        
        # Write mermaid code to file
        with open(mermaid_file, 'w') as f:
            f.write(diagram_code)
        
        # Render to PNG
        try:
            cmd = ['mmdc', '-i', str(mermaid_file), '-o', str(png_file), '-b', 'white']
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"  ✅ Rendered diagram {i+1}")
            
            # Replace mermaid code block with image reference
            original_block = f'```mermaid\n{diagram_code}\n```'
            image_block = f'![Diagram {i+1}]({png_file.name})'
            content = content.replace(original_block, image_block, 1)
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Failed to render diagram {i+1}: {e}")
            # Keep original mermaid block if rendering fails
    
    return content

def clean_content_for_latex(content: str) -> str:
    """Clean content to be LaTeX-compatible."""
    replacements = {
        '✅': '[OK]', '❌': '[ERROR]', '⚠️': '[WARNING]', '🔍': '[SEARCH]',
        '📄': '[FILE]', '📕': '[PDF]', '🎉': '[SUCCESS]', '📊': '[STATS]',
        '🚀': '[DEPLOY]', '🔧': '[CONFIG]', '🆕': '[NEW]', '🎯': '[TARGET]',
        '📤': '[OUTPUT]', '🧪': '[TEST]', '🗑️': '[DELETE]', '📦': '[BUNDLE]',
        '→': '->', '←': '<-', '↑': '^', '↓': 'v', '"': '"', '"': '"',
        ''': "'", ''': "'", '…': '...', '–': '-', '—': '--',
        '├': '|--', '└': '`--', '│': '|', '─': '-', '┌': ',--',
        '┐': '--.', '┘': "--'", '┴': '-+-', '┬': '-+-', '┤': '--|', '┼': '-+-',
    }
    
    for char, replacement in replacements.items():
        content = content.replace(char, replacement)
    
    # Remove remaining non-ASCII characters
    import unicodedata
    content = unicodedata.normalize('NFKD', content)
    content = re.sub(r'[^\x00-\x7F]+', '', content)
    
    return content

def read_markdown_file(file_path: Path) -> str:
    """Read and clean markdown file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return ""

def find_markdown_links(content: str, base_path: Path) -> List[Path]:
    """Find all markdown links in content."""
    links = []
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    for match in re.finditer(link_pattern, content):
        link_path = match.group(2)
        
        if link_path.startswith(('http://', 'https://', '#')):
            continue
            
        if link_path.startswith('./'):
            link_path = link_path[2:]
        elif link_path.startswith('../'):
            resolved_path = base_path.parent / link_path
        else:
            resolved_path = base_path.parent / link_path
            
        try:
            resolved_path = resolved_path.resolve()
            if resolved_path.exists() and resolved_path.suffix == '.md':
                links.append(resolved_path)
        except (OSError, ValueError):
            continue
    
    return links

def collect_all_markdown_files(start_file: Path, visited: Set[Path] = None) -> List[Path]:
    """Recursively collect all markdown files following links."""
    if visited is None:
        visited = set()
    
    if start_file.resolve() in visited:
        return []
    
    visited.add(start_file.resolve())
    files = [start_file]
    
    content = read_markdown_file(start_file)
    linked_files = find_markdown_links(content, start_file)
    
    for linked_file in linked_files:
        if linked_file.resolve() not in visited:
            files.extend(collect_all_markdown_files(linked_file, visited))
    
    return files

def create_combined_markdown(files: List[Path], output_path: Path, diagrams_dir: Path):
    """Create a single markdown file with rendered diagrams."""
    combined_content = []
    
    # Title page
    combined_content.append("""% SMUS CI/CD Pipeline CLI Documentation
% Complete Documentation with Diagrams
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
        if not content:
            continue
        
        # Render diagrams in this file's content
        content = extract_and_render_diagrams(content, diagrams_dir)
        content = clean_content_for_latex(content)
        
        if i > 0:
            combined_content.append("\\newpage\n")
        
        if i == 0:
            header = f"*Source: {rel_path}*\n\n"
            combined_content.append(header + content)
        else:
            section_title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
            header = f"# {section_title}\n\n*Source: {rel_path}*\n\n"
            combined_content.append(header + content)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(combined_content))
    
    print(f"✅ Combined markdown created: {output_path}")

def markdown_to_pdf_pandoc(markdown_path: Path, pdf_path: Path, diagrams_dir: Path):
    """Convert markdown to PDF using pandoc."""
    env = os.environ.copy()
    latex_path = "/usr/local/texlive/2025basic/bin/universal-darwin"
    if latex_path not in env.get("PATH", ""):
        env["PATH"] = f"{latex_path}:{env.get('PATH', '')}"
    
    cmd = [
        'pandoc', str(markdown_path), '-o', str(pdf_path),
        '--pdf-engine=pdflatex', '--toc', '--toc-depth=3', '--number-sections',
        '-V', 'geometry:margin=1in', '-V', 'fontsize=11pt',
        '-V', 'documentclass=article', '-V', 'classoption=oneside',
        f'--resource-path={diagrams_dir}', '--standalone'
    ]
    
    print("Converting to PDF with diagrams...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        print(f"✅ PDF created successfully: {pdf_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Pandoc failed: {e}")
        print(f"stderr: {e.stderr}")
        return False

def main():
    """Main function."""
    if not check_dependencies():
        return 1
    
    start_file = Path('./README.md')
    if not start_file.exists():
        print("❌ Error: README.md not found")
        return 1
    
    print("🔍 Collecting markdown files...")
    markdown_files = collect_all_markdown_files(start_file)
    
    # Add any unlinked markdown files
    project_root = Path('.')
    all_md_files = list(project_root.rglob('*.md'))
    included_files = set(f.resolve() for f in markdown_files)
    
    for md_file in all_md_files:
        if any(part.startswith('.') for part in md_file.parts):
            continue
        if any(part in ['node_modules', '__pycache__', 'output'] for part in md_file.parts):
            continue
        if md_file.resolve() not in included_files:
            markdown_files.append(md_file)
            included_files.add(md_file.resolve())
    
    # Remove duplicates
    seen = set()
    unique_files = []
    for f in markdown_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)
    markdown_files = unique_files
    
    print(f"📄 Found {len(markdown_files)} markdown files")
    
    # Create output directories
    output_dir = Path('./output')
    diagrams_dir = output_dir / 'diagrams'
    output_dir.mkdir(exist_ok=True)
    diagrams_dir.mkdir(exist_ok=True)
    
    # Create combined markdown with rendered diagrams
    combined_md = output_dir / 'smus-cicd-documentation-with-diagrams.md'
    create_combined_markdown(markdown_files, combined_md, diagrams_dir)
    
    # Convert to PDF
    pdf_output = output_dir / 'smus-cicd-documentation-with-diagrams.pdf'
    success = markdown_to_pdf_pandoc(combined_md, pdf_output, diagrams_dir)
    
    if success:
        print(f"\n🎉 Documentation with diagrams compiled successfully!")
        print(f"📄 Markdown: {combined_md}")
        print(f"📕 PDF: {pdf_output}")
        
        md_size = combined_md.stat().st_size
        pdf_size = pdf_output.stat().st_size
        print(f"📊 Sizes: Markdown {md_size:,} bytes, PDF {pdf_size:,} bytes")
        
        # Count diagrams
        diagram_count = len(list(diagrams_dir.glob('*.png')))
        if diagram_count > 0:
            print(f"🖼️  Rendered {diagram_count} diagrams")
        
        return 0
    else:
        print(f"\n⚠️  Markdown created but PDF conversion failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
