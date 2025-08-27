#!/usr/bin/env python3
"""
Create a single PDF from all markdown documents in the SMUS CI/CD pipeline CLI project.
Follows the linking structure starting from README.md.
"""

import os
import re
from pathlib import Path
from typing import List, Set
import subprocess
import sys

def install_dependencies():
    """Install required dependencies."""
    try:
        import markdown
        import weasyprint
    except ImportError:
        print("Installing required dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown", "weasyprint"])
        import markdown
        import weasyprint

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

def read_markdown_file(file_path: Path) -> str:
    """Read markdown file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return ""

def process_markdown_content(content: str, file_path: Path) -> str:
    """Process markdown content to fix relative links and add page breaks."""
    # Add page break before content (except for first document)
    processed_content = f"\n\n---\n\n# {file_path.name}\n\n{content}\n\n"
    
    # Fix relative links to be absolute or remove them
    def fix_link(match):
        link_text = match.group(1)
        link_path = match.group(2)
        
        # Keep external links as-is
        if link_path.startswith(('http://', 'https://')):
            return match.group(0)
        
        # For internal links, just keep the text or make it a reference
        if link_path.endswith('.md'):
            return f"**{link_text}**"
        else:
            return match.group(0)
    
    processed_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', fix_link, processed_content)
    
    return processed_content

def collect_all_markdown_files(start_file: Path, visited: Set[Path] = None) -> List[Path]:
    """Recursively collect all markdown files following the link structure."""
    if visited is None:
        visited = set()
    
    if start_file in visited:
        return []
    
    visited.add(start_file)
    files = [start_file]
    
    # Read the file and find linked markdown files
    content = read_markdown_file(start_file)
    linked_files = find_markdown_links(content, start_file)
    
    # Recursively process linked files
    for linked_file in linked_files:
        if linked_file not in visited:
            files.extend(collect_all_markdown_files(linked_file, visited))
    
    return files

def create_combined_markdown(files: List[Path], output_path: Path):
    """Create a single markdown file from all collected files."""
    combined_content = []
    
    # Add title page
    combined_content.append("""# SMUS CI/CD Pipeline CLI Documentation

Complete documentation compiled from all markdown files in the project.

Generated on: """ + str(subprocess.check_output(['date'], text=True).strip()) + """

---

""")
    
    for i, file_path in enumerate(files):
        print(f"Processing: {file_path}")
        content = read_markdown_file(file_path)
        
        if content:
            # Add section header
            if i == 0:
                # For README, use the original title
                processed_content = content
            else:
                # For other files, add a clear section break
                processed_content = f"\n\n\\pagebreak\n\n# {file_path.stem.replace('-', ' ').title()}\n\n*Source: {file_path.relative_to(Path.cwd())}*\n\n{content}"
            
            # Process the content to fix links
            processed_content = process_markdown_content(processed_content, file_path)
            combined_content.append(processed_content)
    
    # Write combined markdown
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(combined_content))
    
    print(f"Combined markdown created: {output_path}")

def markdown_to_pdf(markdown_path: Path, pdf_path: Path):
    """Convert markdown to PDF using pandoc if available, otherwise use weasyprint."""
    try:
        # Try pandoc first (better PDF output)
        subprocess.run(['pandoc', '--version'], check=True, capture_output=True)
        
        cmd = [
            'pandoc',
            str(markdown_path),
            '-o', str(pdf_path),
            '--pdf-engine=weasyprint',
            '--toc',
            '--toc-depth=3',
            '--number-sections',
            '-V', 'geometry:margin=1in',
            '-V', 'fontsize=11pt',
            '--highlight-style=github'
        ]
        
        print("Converting to PDF using pandoc...")
        subprocess.run(cmd, check=True)
        print(f"PDF created successfully: {pdf_path}")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Pandoc not available, using markdown + weasyprint...")
        
        # Fallback to markdown + weasyprint
        try:
            import markdown
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            # Read markdown content
            with open(markdown_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Convert markdown to HTML
            md = markdown.Markdown(extensions=['codehilite', 'tables', 'toc'])
            html_content = md.convert(md_content)
            
            # Add CSS styling
            css_content = """
            @page {
                margin: 1in;
                @bottom-center {
                    content: counter(page);
                }
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: none;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #2c3e50;
                margin-top: 2em;
                margin-bottom: 1em;
            }
            h1 { font-size: 2em; border-bottom: 2px solid #3498db; padding-bottom: 0.3em; }
            h2 { font-size: 1.5em; border-bottom: 1px solid #bdc3c7; padding-bottom: 0.3em; }
            code {
                background-color: #f8f9fa;
                padding: 0.2em 0.4em;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            }
            pre {
                background-color: #f8f9fa;
                padding: 1em;
                border-radius: 5px;
                overflow-x: auto;
                border-left: 4px solid #3498db;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 0.5em;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            blockquote {
                border-left: 4px solid #3498db;
                margin: 1em 0;
                padding-left: 1em;
                color: #666;
            }
            """
            
            # Create full HTML document
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>SMUS CI/CD Pipeline CLI Documentation</title>
                <style>{css_content}</style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            # Convert to PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=full_html)
            css_doc = CSS(string=css_content, font_config=font_config)
            
            html_doc.write_pdf(str(pdf_path), stylesheets=[css_doc], font_config=font_config)
            print(f"PDF created successfully: {pdf_path}")
            
        except Exception as e:
            print(f"Error creating PDF: {e}")
            print("Please install pandoc for better PDF generation:")
            print("  macOS: brew install pandoc")
            print("  Ubuntu: sudo apt-get install pandoc")
            print("  Windows: Download from https://pandoc.org/installing.html")

def main():
    """Main function to create PDF from markdown files."""
    # Install dependencies
    install_dependencies()
    
    # Start from README.md
    start_file = Path('./README.md')
    if not start_file.exists():
        print("Error: README.md not found in current directory")
        return 1
    
    print("Collecting markdown files following link structure...")
    
    # Collect all markdown files
    markdown_files = collect_all_markdown_files(start_file)
    
    # Also add any markdown files that might not be linked
    project_root = Path('.')
    all_md_files = list(project_root.rglob('*.md'))
    
    # Add files that weren't found through links
    for md_file in all_md_files:
        # Skip hidden directories and common exclusions
        if any(part.startswith('.') for part in md_file.parts):
            continue
        if 'node_modules' in md_file.parts or '__pycache__' in md_file.parts:
            continue
        if md_file not in markdown_files:
            markdown_files.append(md_file)
    
    print(f"Found {len(markdown_files)} markdown files:")
    for f in markdown_files:
        print(f"  - {f}")
    
    # Create output directory
    output_dir = Path('./output')
    output_dir.mkdir(exist_ok=True)
    
    # Create combined markdown
    combined_md = output_dir / 'smus-cicd-documentation.md'
    create_combined_markdown(markdown_files, combined_md)
    
    # Convert to PDF
    pdf_output = output_dir / 'smus-cicd-documentation.pdf'
    markdown_to_pdf(combined_md, pdf_output)
    
    print(f"\n✅ Documentation compiled successfully!")
    print(f"📄 Markdown: {combined_md}")
    print(f"📕 PDF: {pdf_output}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
