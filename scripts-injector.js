#!/usr/bin/env node
/**
 * Scripts Injector - Dynamic package.json script injection
 * מזריק סקריפטים - הזרקה דינמית של סקריפטים ל-package.json
 */

const fs = require('fs');
const path = require('path');

console.log('🔧 Scripts Injector - Injecting deployment scripts');

try {
    const packagePath = path.join(__dirname, 'package.json');
    
    if (!fs.existsSync(packagePath)) {
        console.error('❌ package.json not found');
        process.exit(1);
    }
    
    const packageData = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    
    // Backup original scripts
    const originalScripts = { ...packageData.scripts };
    
    // Inject our deployment scripts
    packageData.scripts = {
        ...originalScripts,
        "build": "node npm-build.js",
        "start": "node npm-start.js",
        "dev": "python main.py & node baileys_client.js",
        "deploy-build": "node deploy.js build",
        "deploy-start": "node deploy.js start"
    };
    
    // Write back with proper formatting
    fs.writeFileSync(packagePath, JSON.stringify(packageData, null, 2));
    
    console.log('✅ Scripts injected successfully:');
    console.log('  - build: node npm-build.js');
    console.log('  - start: node npm-start.js'); 
    console.log('  - deploy-build: node deploy.js build');
    console.log('  - deploy-start: node deploy.js start');
    
} catch (error) {
    console.error('❌ Script injection failed:', error.message);
    process.exit(1);
}