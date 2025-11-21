#!/usr/bin/env python3
"""
Batch translate README.md to multiple languages using AWS Bedrock.
This script preserves markdown structure, code blocks, and technical terms.
"""

import boto3
import json
import os
import sys
from pathlib import Path

# Language configurations
LANGUAGES = {
    'fr': {'name': 'French', 'native': 'Français'},
    'he': {'name': 'Hebrew', 'native': 'עברית'},
    'it': {'name': 'Italian', 'native': 'Italiano'},
    'ja': {'name': 'Japanese', 'native': '日本語'},
    'zh': {'name': 'Chinese', 'native': '中文'},
}

TRANSLATION_PROMPT = """Translate the following markdown document to {language}.

CRITICAL REQUIREMENTS:
1. Preserve EXACT markdown structure:
   - Same number of headers (# ## ###)
   - Same header hierarchy
   - Same number of code blocks with IDENTICAL content
   - Same number of lists, tables, sections
   - All emojis in same positions (✅ 👨‍💻 🚀 etc.)
   - All horizontal rules (---) in same positions
   - All HTML comments and collapsible sections

2. DO NOT translate:
   - Code blocks (bash, yaml, python, etc.) - keep 100% identical
   - Command names: smus-cli, git, pip, etc.
   - File names: manifest.yaml, README.md, etc.
   - URLs and links
   - AWS service names: SageMaker, Glue, Athena, DataZone, S3, etc.
   - Technical terms: CLI, CI/CD, DevOps, workflow, pipeline, bundle, manifest
   - Variable names and parameters

3. TRANSLATE naturally:
   - Descriptive text and explanations
   - Section headings (but keep technical terms in English)
   - User-facing messages
   - Documentation prose

4. Maintain exact formatting:
   - Line breaks
   - Indentation
   - List markers
   - Table structure

Document to translate:

{content}
"""

def translate_with_bedrock(content: str, target_lang: str, lang_name: str) -> str:
    """Translate content using AWS Bedrock Claude."""
    bedrock = boto3.client('bedrock-runtime')
    
    prompt = TRANSLATION_PROMPT.format(
        language=lang_name,
        content=content
    )
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200000,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
    }
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        translated_text = response_body['content'][0]['text']
        
        return translated_text
    
    except Exception as e:
        print(f"Error translating to {target_lang}: {e}")
        return None

def main():
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Read source README
    readme_path = project_root / "README.md"
    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}")
        sys.exit(1)
    
    print(f"Reading {readme_path}...")
    with open(readme_path, 'r', encoding='utf-8') as f:
        source_content = f.read()
    
    print(f"Source README: {len(source_content)} characters, {len(source_content.splitlines())} lines\n")
    
    # Translate to each language
    for lang_code, lang_info in LANGUAGES.items():
        print(f"Translating to {lang_info['name']} ({lang_code})...")
        
        translated = translate_with_bedrock(
            source_content,
            lang_code,
            lang_info['name']
        )
        
        if translated:
            # Save translation
            output_dir = project_root / "docs" / "langs" / lang_code
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "README.md"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated)
            
            print(f"✅ Saved to {output_path}")
            print(f"   {len(translated)} characters, {len(translated.splitlines())} lines\n")
        else:
            print(f"❌ Failed to translate to {lang_code}\n")

if __name__ == "__main__":
    main()
