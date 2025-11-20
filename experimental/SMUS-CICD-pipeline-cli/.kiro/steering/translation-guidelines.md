---
inclusion: manual
---

# Documentation Translation Guidelines

When translating documentation files:

## Target Languages
- French (fr)
- Hebrew (he) 
- Italian (it)
- Japanese (ja)
- Portuguese (pt)
- Chinese (zh)

## Translation Rules

1. **Preserve Structure**: Keep all markdown formatting, headers, lists, tables, and code blocks exactly as they are
2. **Code Blocks**: Never translate content inside code blocks, command examples, or file paths
3. **Technical Terms**: Keep these in English:
   - AWS service names (S3, Lambda, CloudFormation, etc.)
   - CLI command names (smus-deploy, git, etc.)
   - Programming language keywords
   - Configuration keys and parameters
4. **URLs and Links**: Keep all URLs unchanged, translate link text only
5. **File Paths**: Keep file paths in English
6. **Avoid Language Mixing**: 
   - If a sentence contains multiple English technical terms, keep the ENTIRE sentence in English
   - Add translation in parentheses after the English sentence when helpful
   - Example: "Deploy Airflow DAGs, Jupyter notebooks, and ML workflows (פרוס DAGs של Airflow, מחברות Jupyter, וזרימות עבודה של ML)"
   - Only translate sentences that are purely descriptive with minimal technical terms
   - Never switch languages mid-sentence - it's confusing and hard to read
7. **Natural Translation**: Translate prose naturally for each language, not word-for-word, but only when sentences are not heavily technical
8. **Hebrew RTL**: Wrap entire Hebrew document in `<div dir="rtl">...</div>` for proper right-to-left text direction
9. **Output Location**: Save to `docs/langs/{language-code}/` maintaining the same subdirectory structure as the source

## Directory Structure
- Source: `README.md` → Translations: `docs/langs/fr/README.md`, `docs/langs/he/README.md`, etc.
- Source: `docs/cli-commands.md` → Translations: `docs/langs/fr/cli-commands.md`, etc.
- Source: `developer/guide.md` → Translations: `docs/langs/fr/developer/guide.md`, etc.
