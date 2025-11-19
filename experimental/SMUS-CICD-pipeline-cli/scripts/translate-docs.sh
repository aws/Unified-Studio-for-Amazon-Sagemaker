#!/bin/bash

# Translation script for SMUS CI/CD documentation
# Usage: ./scripts/translate-docs.sh <lang_code>
# Supported: pt (Portuguese), fr (French), it (Italian), ja (Japanese), zh (Chinese), he (Hebrew)

set -e

LANG_CODE=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_README="$PROJECT_ROOT/README.md"
TARGET_DIR="$PROJECT_ROOT/docs/langs/$LANG_CODE"
TARGET_README="$TARGET_DIR/README.md"

# Language names
declare -A LANG_NAMES=(
    ["pt"]="Português (Brasil)"
    ["fr"]="Français"
    ["it"]="Italiano"
    ["ja"]="日本語"
    ["zh"]="中文"
    ["he"]="עברית"
)

# Validation
if [ -z "$LANG_CODE" ]; then
    echo "Usage: $0 <lang_code>"
    echo "Supported languages: pt, fr, it, ja, zh, he"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Language directory $TARGET_DIR does not exist"
    exit 1
fi

if [ ! -f "$SOURCE_README" ]; then
    echo "Error: Source README not found at $SOURCE_README"
    exit 1
fi

echo "========================================="
echo "Translating README to ${LANG_NAMES[$LANG_CODE]}"
echo "========================================="
echo ""

# Count sections in source
SOURCE_SECTIONS=$(grep -c "^## " "$SOURCE_README" || true)
SOURCE_EXAMPLES=$(grep -c "^### 📊\|^### 📓\|^### 🤖\|^### 🧠" "$SOURCE_README" || true)
SOURCE_DETAILS=$(grep -c "<details>" "$SOURCE_README" || true)

echo "Source README structure:"
echo "  - Major sections (##): $SOURCE_SECTIONS"
echo "  - Examples: $SOURCE_EXAMPLES"
echo "  - Collapsible sections: $SOURCE_DETAILS"
echo ""

# Create translation prompt
TRANSLATION_PROMPT="Translate the following README from English to ${LANG_NAMES[$LANG_CODE]}.

CRITICAL RULES:
1. Keep ALL technical terms in English: pipeline, deploy, workflow, manifest, bundle, stage, CLI, CI/CD, DevOps, etc.
2. Keep ALL code blocks unchanged (including bash, yaml, markdown examples)
3. Keep ALL URLs unchanged
4. Keep ALL command examples unchanged
5. Translate ONLY descriptive text, headings, and explanations
6. Maintain exact same structure: same sections, same order, same formatting
7. Keep all <details> tags and HTML unchanged
8. Keep all markdown formatting (**, ##, ###, etc.)

For ${LANG_CODE}:
$([ "$LANG_CODE" = "he" ] && echo "- Note: Hebrew is RTL but keep technical terms LTR")
$([ "$LANG_CODE" = "ja" ] || [ "$LANG_CODE" = "zh" ] && echo "- Keep technical terms in English even though they may have local equivalents")

Now translate this README:

---
$(cat "$SOURCE_README")
---

Output ONLY the translated README, no explanations."

echo "Calling Q CLI for translation..."
echo ""

# Call Q CLI for translation
q chat "$TRANSLATION_PROMPT" > "$TARGET_README.tmp"

# Verify translation
echo ""
echo "Verifying translation..."

if [ ! -f "$TARGET_README.tmp" ]; then
    echo "Error: Translation failed - no output file"
    exit 1
fi

TARGET_SECTIONS=$(grep -c "^## " "$TARGET_README.tmp" || true)
TARGET_EXAMPLES=$(grep -c "^### 📊\|^### 📓\|^### 🤖\|^### 🧠" "$TARGET_README.tmp" || true)
TARGET_DETAILS=$(grep -c "<details>" "$TARGET_README.tmp" || true)

echo "Translated README structure:"
echo "  - Major sections (##): $TARGET_SECTIONS"
echo "  - Examples: $TARGET_EXAMPLES"
echo "  - Collapsible sections: $TARGET_DETAILS"
echo ""

# Verification checks
VERIFICATION_PASSED=true

if [ "$SOURCE_SECTIONS" -ne "$TARGET_SECTIONS" ]; then
    echo "❌ VERIFICATION FAILED: Section count mismatch"
    echo "   Expected: $SOURCE_SECTIONS, Got: $TARGET_SECTIONS"
    VERIFICATION_PASSED=false
fi

if [ "$SOURCE_EXAMPLES" -ne "$TARGET_EXAMPLES" ]; then
    echo "❌ VERIFICATION FAILED: Example count mismatch"
    echo "   Expected: $SOURCE_EXAMPLES, Got: $TARGET_EXAMPLES"
    VERIFICATION_PASSED=false
fi

if [ "$SOURCE_DETAILS" -ne "$TARGET_DETAILS" ]; then
    echo "❌ VERIFICATION FAILED: Collapsible section count mismatch"
    echo "   Expected: $SOURCE_DETAILS, Got: $TARGET_DETAILS"
    VERIFICATION_PASSED=false
fi

# Check for code blocks
SOURCE_CODE_BLOCKS=$(grep -c '```' "$SOURCE_README" || true)
TARGET_CODE_BLOCKS=$(grep -c '```' "$TARGET_README.tmp" || true)

if [ "$SOURCE_CODE_BLOCKS" -ne "$TARGET_CODE_BLOCKS" ]; then
    echo "❌ VERIFICATION FAILED: Code block count mismatch"
    echo "   Expected: $SOURCE_CODE_BLOCKS, Got: $TARGET_CODE_BLOCKS"
    VERIFICATION_PASSED=false
fi

if [ "$VERIFICATION_PASSED" = true ]; then
    echo "✅ Verification passed!"
    mv "$TARGET_README.tmp" "$TARGET_README"
    echo ""
    echo "Translation saved to: $TARGET_README"
    echo ""
    echo "Next steps:"
    echo "1. Review the translation for accuracy"
    echo "2. Update language selector in main README"
    echo "3. Commit and push changes"
else
    echo ""
    echo "Translation saved to: $TARGET_README.tmp (for review)"
    echo "Please review and fix issues before using"
    exit 1
fi
