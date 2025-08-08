#!/usr/bin/env node
/**
 * NPM Build Script - Wrapper for Hebrew CRM deployment
 * סקריפט בניה עבור NPM - עוטף לפריסת CRM עברית
 */

;
;

const { execSync } = require('child_process');

try {
    // Run the deployment build
    ;
    execSync('node deploy.js build', { stdio: 'inherit' });
    
    ;
    process.exit(0);
    
} catch (error) {
    console.error('❌ NPM build failed:', error.message);
    process.exit(1);
}