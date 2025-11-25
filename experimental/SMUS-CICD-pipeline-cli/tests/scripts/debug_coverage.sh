#!/bin/bash
# Debug script for coverage file issues

echo "=== Coverage Debug Info ==="
echo ""

echo "📁 Current directory:"
pwd
echo ""

echo "📊 Looking for coverage data files (.data):"
find . -name "coverage-*.data" -type f | while read f; do
    echo "  ✓ $f ($(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null) bytes)"
done
echo ""

echo "📊 Looking for coverage XML files:"
find . -name "coverage-*.xml" -type f | while read f; do
    echo "  ✓ $f ($(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null) bytes)"
done
echo ""

echo "📊 Looking for hidden .coverage files:"
find . -name ".coverage*" -type f | while read f; do
    echo "  ✓ $f ($(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null) bytes)"
done
echo ""

echo "📦 Directory structure:"
ls -laR | head -100
echo ""

echo "🔍 Coverage tool version:"
coverage --version || echo "  ❌ coverage not installed"
echo ""

echo "=== End Debug Info ==="
