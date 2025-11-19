# Translated Documentation

This directory contains translations of the SMUS CI/CD Pipeline CLI documentation.

## Available Languages

| Language | Code | README |
|----------|------|--------|
| Portuguese (Brazil) | `pt` | [README.md](pt/README.md) |
| French | `fr` | [README.md](fr/README.md) |
| Italian | `it` | [README.md](it/README.md) |
| Japanese | `ja` | [README.md](ja/README.md) |
| Chinese | `zh` | [README.md](zh/README.md) |
| Hebrew | `he` | [README.md](he/README.md) |

## Translation Guidelines

### What Gets Translated
- Descriptive text and explanations
- Section headings and titles
- User-facing messages
- Documentation prose

### What Stays in English
- **Technical terms**: pipeline, deploy, workflow, manifest, bundle, stage, CLI, CI/CD, DevOps, etc.
- **Code blocks**: All bash, YAML, Python examples
- **Commands**: `smus-cli deploy`, `git clone`, etc.
- **URLs**: All links remain unchanged
- **File paths**: `manifest.yaml`, `README.md`, etc.
- **AWS service names**: SageMaker, Glue, Athena, etc.

### Translation Process

Use the translation script:

```bash
# From project root
./scripts/translate-docs.sh <lang_code>

# Examples
./scripts/translate-docs.sh fr  # French
./scripts/translate-docs.sh ja  # Japanese
./scripts/translate-docs.sh he  # Hebrew
```

The script will:
1. Call Q CLI to translate the main README
2. Verify structure matches (sections, examples, collapsible elements)
3. Check code block count
4. Save translation only if verification passes

### Manual Review Required

After translation, please review:
- Technical accuracy of translated descriptions
- Cultural appropriateness
- Proper handling of RTL languages (Hebrew)
- Links work correctly with new paths

### Updating Translations

When the English README changes:

```bash
# Re-run translation for specific language
./scripts/translate-docs.sh pt

# Or update all languages
for lang in pt fr it ja zh he; do
  ./scripts/translate-docs.sh $lang
done
```

## Contributing

To add a new language:

1. Create folder: `mkdir docs/langs/<lang_code>`
2. Run translation: `./scripts/translate-docs.sh <lang_code>`
3. Update language selector in main README
4. Add entry to this README

## Language Codes

Following ISO 639-1 standard:
- `pt` - Portuguese (Brazil)
- `fr` - French
- `it` - Italian
- `ja` - Japanese
- `zh` - Chinese (Simplified)
- `he` - Hebrew
- `es` - Spanish (future)
- `de` - German (future)
- `ko` - Korean (future)
