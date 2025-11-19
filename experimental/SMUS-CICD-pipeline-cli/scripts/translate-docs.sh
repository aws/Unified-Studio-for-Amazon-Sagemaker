#!/usr/bin/env bash

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

# Language names function
get_lang_name() {
    case $1 in
        pt) echo "Português (Brasil)" ;;
        fr) echo "Français" ;;
        it) echo "Italiano" ;;
        ja) echo "日本語" ;;
        zh) echo "中文" ;;
        he) echo "עברית" ;;
        *) echo "Unknown" ;;
    esac
}

LANG_NAME=$(get_lang_name "$LANG_CODE")

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
echo "Translating README to $LANG_NAME"
echo "========================================="
echo ""
echo "NOTE: This will use Q CLI to translate the README."
echo "The translation may take a few minutes due to the file size."
echo ""

# Count sections in source
SOURCE_SECTIONS=$(grep -c "^## " "$SOURCE_README" || true)
SOURCE_EXAMPLES=$(grep -c "^### 📊\|^### 📓\|^### 🤖\|^### 🧠" "$SOURCE_README" || true)
SOURCE_DETAILS=$(grep -c "<details>" "$SOURCE_README" || true)
SOURCE_CODE_BLOCKS=$(grep -c '```' "$SOURCE_README" || true)

echo "Source README structure:"
echo "  - Major sections (##): $SOURCE_SECTIONS"
echo "  - Examples: $SOURCE_EXAMPLES"
echo "  - Collapsible sections: $SOURCE_DETAILS"
echo "  - Code blocks: $SOURCE_CODE_BLOCKS"
echo ""

# Create a temporary prompt file
PROMPT_FILE=$(mktemp)
cat > "$PROMPT_FILE" << 'PROMPT_END'
Translate the README from English to TARGET_LANG_NAME.

CRITICAL TRANSLATION RULES:
1. Keep ALL technical terms in English: pipeline, deploy, workflow, manifest, bundle, stage, CLI, CI/CD, DevOps, SageMaker, Glue, Athena, QuickSight, Bedrock, MWAA, DataZone, EventBridge, MLflow, etc.
2. Keep ALL code blocks COMPLETELY unchanged (bash, yaml, json examples)
3. Keep ALL URLs unchanged
4. Keep ALL command examples unchanged (smus-cli deploy, git clone, pip install, etc.)
5. Keep ALL file paths unchanged (manifest.yaml, README.md, docs/, etc.)
6. Translate ONLY descriptive text, headings, and explanations
7. Maintain EXACT same structure: same sections, same order, same formatting
8. Keep ALL <details> and </details> tags unchanged
9. Keep ALL HTML unchanged
10. Keep ALL markdown formatting unchanged (**, ##, ###, [], (), etc.)
11. Keep ALL emojis unchanged (📊, 📓, 🤖, 🧠, ✅, etc.)

LANG_SPECIFIC_NOTES

Read the following English README and output ONLY the translated version. Do not add any explanations or comments.

PROMPT_END

# Add language-specific notes
LANG_NOTES=""
if [ "$LANG_CODE" = "he" ]; then
    LANG_NOTES="- Hebrew is RTL but keep ALL technical terms in LTR English"
elif [ "$LANG_CODE" = "ja" ] || [ "$LANG_CODE" = "zh" ]; then
    LANG_NOTES="- Keep technical terms in English even though local equivalents may exist"
fi

sed -i.bak "s/TARGET_LANG_NAME/$LANG_NAME/g" "$PROMPT_FILE"
sed -i.bak "s/LANG_SPECIFIC_NOTES/$LANG_NOTES/g" "$PROMPT_FILE"

# Append the source README
echo "" >> "$PROMPT_FILE"
echo "---" >> "$PROMPT_FILE"
cat "$SOURCE_README" >> "$PROMPT_FILE"
echo "---" >> "$PROMPT_FILE"

echo "Calling Q CLI for translation (this may take a few minutes)..."
echo ""

# Call Q CLI - note: this might fail if README is too large
if q chat "$(cat "$PROMPT_FILE")" > "$TARGET_README.tmp" 2>&1; then
    echo ""
    echo "Translation completed. Verifying..."
    
    # Verify translation
    if [ ! -f "$TARGET_README.tmp" ] || [ ! -s "$TARGET_README.tmp" ]; then
        echo "❌ Error: Translation failed - no output or empty file"
        rm -f "$PROMPT_FILE" "$PROMPT_FILE.bak"
        exit 1
    fi
    
    TARGET_SECTIONS=$(grep -c "^## " "$TARGET_README.tmp" || true)
    TARGET_EXAMPLES=$(grep -c "^### 📊\|^### 📓\|^### 🤖\|^### 🧠" "$TARGET_README.tmp" || true)
    TARGET_DETAILS=$(grep -c "<details>" "$TARGET_README.tmp" || true)
    TARGET_CODE_BLOCKS=$(grep -c '```' "$TARGET_README.tmp" || true)
    
    echo ""
    echo "Translated README structure:"
    echo "  - Major sections (##): $TARGET_SECTIONS"
    echo "  - Examples: $TARGET_EXAMPLES"
    echo "  - Collapsible sections: $TARGET_DETAILS"
    echo "  - Code blocks: $TARGET_CODE_BLOCKS"
    echo ""
    
    # Verification checks
    VERIFICATION_PASSED=true
    
    if [ "$SOURCE_SECTIONS" -ne "$TARGET_SECTIONS" ]; then
        echo "⚠️  WARNING: Section count mismatch"
        echo "   Expected: $SOURCE_SECTIONS, Got: $TARGET_SECTIONS"
        VERIFICATION_PASSED=false
    fi
    
    if [ "$SOURCE_EXAMPLES" -ne "$TARGET_EXAMPLES" ]; then
        echo "⚠️  WARNING: Example count mismatch"
        echo "   Expected: $SOURCE_EXAMPLES, Got: $TARGET_EXAMPLES"
        VERIFICATION_PASSED=false
    fi
    
    if [ "$SOURCE_DETAILS" -ne "$TARGET_DETAILS" ]; then
        echo "⚠️  WARNING: Collapsible section count mismatch"
        echo "   Expected: $SOURCE_DETAILS, Got: $TARGET_DETAILS"
        VERIFICATION_PASSED=false
    fi
    
    if [ "$SOURCE_CODE_BLOCKS" -ne "$TARGET_CODE_BLOCKS" ]; then
        echo "⚠️  WARNING: Code block count mismatch"
        echo "   Expected: $SOURCE_CODE_BLOCKS, Got: $TARGET_CODE_BLOCKS"
        VERIFICATION_PASSED=false
    fi
    
    if [ "$VERIFICATION_PASSED" = true ]; then
        echo "✅ Verification passed!"
        mv "$TARGET_README.tmp" "$TARGET_README"
        echo ""
        echo "Translation saved to: $TARGET_README"
        echo ""
        echo "Please review the translation for:"
        echo "  - Technical accuracy"
        echo "  - Proper handling of technical terms (should be in English)"
        echo "  - Links work correctly"
    else
        echo ""
        echo "⚠️  Verification warnings detected"
        echo "Translation saved to: $TARGET_README.tmp"
        echo ""
        echo "Please review manually before accepting:"
        echo "  mv $TARGET_README.tmp $TARGET_README"
    fi
else
    echo "❌ Error: Q CLI translation failed"
    echo "This might be because the README is too large for a single Q CLI call"
    echo ""
    echo "Alternative: Use the Portuguese translation as a template and manually translate"
    rm -f "$PROMPT_FILE" "$PROMPT_FILE.bak"
    exit 1
fi

# Cleanup
rm -f "$PROMPT_FILE" "$PROMPT_FILE.bak"
