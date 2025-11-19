#!/usr/bin/env python3
"""
Translate README.md in chunks to handle large files.
Splits by major sections (##) and translates each independently.
"""

import boto3
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

LANGUAGES = {
    'fr': 'French',
    'he': 'Hebrew',
    'it': 'Italian',
    'ja': 'Japanese',
    'zh': 'Chinese (Simplified)',
}

def split_into_sections(content: str) -> List[Tuple[str, str]]:
    """Split markdown by ## headers, keeping structure."""
    sections = []
    current_section = []
    current_header = "header"
    
    lines = content.split('\n')
    for line in lines:
        if line.startswith('## '):
            # Save previous section
            if current_section:
                sections.append((current_header, '\n'.join(current_section)))
            # Start new section
            current_header = line
            current_section = [line]
        else:
            current_section.append(line)
    
    # Add last section
    if current_section:
        sections.append((current_header, '\n'.join(current_section)))
    
    return sections

def translate_chunk(content: str, language: str) -> str:
    """Translate a chunk using Bedrock."""
    bedrock = boto3.client('bedrock-runtime')
    
    prompt = f"""Translate to {language}. Output ONLY translated markdown, no explanations.

RULES:
- Keep code blocks, commands, file names, URLs, AWS services unchanged
- Keep technical terms: CLI, CI/CD, DevOps, workflow, pipeline, bundle, manifest
- Translate descriptive text naturally
- Preserve ALL markdown formatting exactly

{content}"""
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    
    try:
        response = bedrock.invoke_model(
            modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(request_body)
        )
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text'].strip()
    except Exception as e:
        print(f"  Error: {e}")
        return content  # Return original on error

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    readme_path = project_root / "README.md"
    
    print(f"Reading {readme_path}...")
    with open(readme_path, 'r', encoding='utf-8') as f:
        source_content = f.read()
    
    print(f"Source: {len(source_content)} chars, {len(source_content.splitlines())} lines\n")
    
    # Split into sections
    sections = split_into_sections(source_content)
    print(f"Split into {len(sections)} sections\n")
    
    for lang_code, lang_name in LANGUAGES.items():
        print(f"Translating to {lang_name} ({lang_code})...")
        translated_sections = []
        
        for i, (header, section_content) in enumerate(sections, 1):
            print(f"  Section {i}/{len(sections)}: {header[:50]}...")
            translated = translate_chunk(section_content, lang_name)
            translated_sections.append(translated)
        
        # Combine sections
        full_translation = '\n\n'.join(translated_sections)
        
        # Save
        output_dir = project_root / "docs" / "langs" / lang_code
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "README.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_translation)
        
        print(f"✅ Saved: {len(full_translation)} chars, {len(full_translation.splitlines())} lines\n")

if __name__ == "__main__":
    main()
