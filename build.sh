#!/bin/bash
# Hebrew AI Call Center Build Script
# סקריפט בנייה למערכת AI מוקד שיחות עברית

echo "🚀 Building Hebrew AI Call Center System..."

# Step 1: Install client dependencies
echo "📦 Installing client dependencies..."
cd client
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install client dependencies"
    exit 1
fi

# Step 2: Build React frontend
echo "🏗️ Building React frontend..."
npm run build
if [ $? -ne 0 ]; then
    echo "❌ Failed to build React frontend"
    exit 1
fi

cd ..

# Step 3: Verify build
echo "✅ Verifying build..."
if [ -d "client/dist" ]; then
    echo "✅ React build successful - dist directory created"
    ls -la client/dist/
else
    echo "❌ Build failed - no dist directory found"
    exit 1
fi

echo "🎉 Build completed successfully!"
echo "🚀 Ready for deployment!"