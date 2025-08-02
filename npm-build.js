#!/usr/bin/env node
/**
 * NPM Build Script - Wrapper for Hebrew CRM deployment
 * סקריפט בניה עבור NPM - עוטף לפריסת CRM עברית
 */

console.log('🚀 Hebrew AI Call Center CRM - NPM Build Wrapper');
console.log('=================================================');

const { execSync } = require('child_process');

try {
    // Run the deployment build
    console.log('📦 Running deployment build...');
    execSync('node deploy.js build', { stdio: 'inherit' });
    
    console.log('✅ NPM build completed successfully!');
    process.exit(0);
    
} catch (error) {
    console.error('❌ NPM build failed:', error.message);
    process.exit(1);
}