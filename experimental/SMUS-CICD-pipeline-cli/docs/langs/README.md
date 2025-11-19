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

### Automated Translation with Kiro Agent Hooks

**NEW**: Documentation is now automatically translated when you save files using a Kiro agent hook!

#### How It Works
1. Edit any documentation file (README.md, docs/*.md, developer/*.md)
2. Save the file
3. The agent hook triggers automatically
4. Translations are generated for all 6 languages
5. Files are saved to `docs/langs/{language}/` with the same structure

#### Manual Translation
You can also manually trigger translation by asking Kiro:
```
Translate docs/cli-commands.md to all languages
```

#### Legacy Script (Optional)
The translation script is still available:

```bash
# From project root
./scripts/translate-docs.sh <lang_code>

# Examples
./scripts/translate-docs.sh fr  # French
./scripts/translate-docs.sh ja  # Japanese
./scripts/translate-docs.sh he  # Hebrew
```

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
