#!/usr/bin/env node
/**
 * NPM Start Script - Wrapper for Hebrew CRM production
 * סקריפט הפעלה עבור NPM - עוטף לייצור CRM עברית
 */

console.log('🚀 Hebrew AI Call Center CRM - NPM Start Wrapper');
console.log('=================================================');

const { spawn } = require('child_process');

try {
    // Run the deployment start
    console.log('🌟 Starting production server...');
    const process = spawn('node', ['deploy.js', 'start'], { stdio: 'inherit' });
    
    process.on('exit', (code) => {
        console.log(`Production server exited with code ${code}`);
        process.exit(code);
    });
    
} catch (error) {
    console.error('❌ NPM start failed:', error.message);
    process.exit(1);
}