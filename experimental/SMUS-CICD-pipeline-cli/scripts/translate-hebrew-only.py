#!/usr/bin/env python3
"""Re-translate Hebrew README with improved style."""

import boto3
import json
from pathlib import Path

def translate_chunk(content: str) -> str:
    """Translate a chunk using Bedrock."""
    bedrock = boto3.client('bedrock-runtime')
    
    prompt = f"""Translate to Hebrew. Output ONLY translated markdown, no explanations.

CRITICAL RULES:
- Keep code blocks, commands, file names, URLs, AWS services unchanged
- Keep technical terms: CLI, CI/CD, DevOps, workflow, pipeline, bundle, manifest, SageMaker, Glue, Athena, DataZone, S3
- AVOID LANGUAGE MIXING: If a sentence has multiple English technical terms, keep ENTIRE sentence in English and add Hebrew translation in parentheses after
- Example: "Deploy Airflow DAGs, Jupyter notebooks, and ML workflows" → Keep in English, then add: (פרוס DAGs של Airflow, מחברות Jupyter, וזרימות עבודה של ML)
- Only translate purely descriptive sentences with minimal technical terms
- Never switch languages mid-sentence - it's confusing
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
        return content

def split_into_sections(content: str):
    """Split markdown by ## headers."""
    sections = []
    current_section = []
    current_header = "header"
    
    lines = content.split('\n')
    for line in lines:
        if line.startswith('## '):
            if current_section:
                sections.append((current_header, '\n'.join(current_section)))
            current_header = line
            current_section = [line]
        else:
            current_section.append(line)
    
    if current_section:
        sections.append((current_header, '\n'.join(current_section)))
    
    return sections

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    readme_path = project_root / "README.md"
    
    print(f"Reading {readme_path}...")
    with open(readme_path, 'r', encoding='utf-8') as f:
        source_content = f.read()
    
    # Remove existing language badges from source
    lines = source_content.split('\n')
    clean_lines = [l for l in lines if not l.startswith('[![')]
    source_content = '\n'.join(clean_lines)
    
    sections = split_into_sections(source_content)
    print(f"Split into {len(sections)} sections\n")
    
    print("Translating to Hebrew...")
    translated_sections = []
    
    for i, (header, section_content) in enumerate(sections, 1):
        print(f"  Section {i}/{len(sections)}: {header[:50]}...")
        translated = translate_chunk(section_content)
        translated_sections.append(translated)
    
    # Combine sections
    full_translation = '\n\n'.join(translated_sections)
    
    # Add language badges
    badges = [
        "[![en](https://img.shields.io/badge/lang-en-gray.svg)](../../../README.md)",
        "[![pt](https://img.shields.io/badge/lang-pt-gray.svg)](../pt/README.md)",
        "[![fr](https://img.shields.io/badge/lang-fr-gray.svg)](../fr/README.md)",
        "[![it](https://img.shields.io/badge/lang-it-gray.svg)](../it/README.md)",
        "[![ja](https://img.shields.io/badge/lang-ja-gray.svg)](../ja/README.md)",
        "[![zh](https://img.shields.io/badge/lang-zh-gray.svg)](../zh/README.md)",
        "[![he](https://img.shields.io/badge/lang-he-brightgreen.svg?style=for-the-badge)](../he/README.md)"
    ]
    
    badge_bar = '\n'.join(badges)
    
    # Wrap in RTL div
    full_translation = f'<div dir="rtl">\n\n{badge_bar}\n\n{full_translation}\n\n</div>'
    
    # Save
    output_dir = project_root / "docs" / "langs" / "he"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "README.md"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_translation)
    
    print(f"✅ Saved: {len(full_translation)} chars, {len(full_translation.splitlines())} lines")

if __name__ == "__main__":
    main()
