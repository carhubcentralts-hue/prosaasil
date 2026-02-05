#!/bin/bash
# Script to clear Python bytecode cache files
# Run this if you encounter import or syntax errors after code updates

echo "🧹 Clearing Python bytecode cache..."

# Find and remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "✓ Removed __pycache__ directories"

# Find and remove all .pyc files
find . -name "*.pyc" -delete 2>/dev/null
echo "✓ Removed .pyc files"

# Find and remove all .pyo files (optimized bytecode)
find . -name "*.pyo" -delete 2>/dev/null
echo "✓ Removed .pyo files"

echo "✅ Python cache cleared successfully!"
echo "   You can now restart your application."
