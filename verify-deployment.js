#!/usr/bin/env node
/**
 * Deployment Verification Script
 * סקריפט אימות פריסה
 */

const fs = require('fs');
const { execSync } = require('child_process');

console.log('🔍 Hebrew AI Call Center CRM - Deployment Verification');
console.log('====================================================');

let allTests = [];

function test(name, fn) {
    try {
        fn();
        console.log(`✅ ${name}`);
        allTests.push({ name, status: 'PASS' });
        return true;
    } catch (error) {
        console.log(`❌ ${name}: ${error.message}`);
        allTests.push({ name, status: 'FAIL', error: error.message });
        return false;
    }
}

// Test 1: Check required files exist
test('Required deployment files exist', () => {
    const requiredFiles = [
        'deploy.js',
        'npm-build.js', 
        'npm-start.js',
        'main.py',
        'app.py',
        'pyproject.toml'
    ];
    
    for (const file of requiredFiles) {
        if (!fs.existsSync(file)) {
            throw new Error(`Missing file: ${file}`);
        }
    }
});

// Test 2: Check Python application structure
test('Python Flask application structure', () => {
    if (!fs.existsSync('main.py')) throw new Error('main.py not found');
    if (!fs.existsSync('app.py')) throw new Error('app.py not found');
    
    const mainContent = fs.readFileSync('main.py', 'utf8');
    if (!mainContent.includes('from app import app')) {
        throw new Error('main.py does not import Flask app');
    }
});

// Test 3: Test build script functionality
test('Build script works', () => {
    try {
        execSync('node deploy.js build', { stdio: 'pipe', timeout: 30000 });
    } catch (error) {
        throw new Error('Build script failed');
    }
});

// Test 4: Check deployment scripts are executable
test('Deployment scripts are executable', () => {
    const scripts = ['deploy.js', 'npm-build.js', 'npm-start.js'];
    for (const script of scripts) {
        const stats = fs.statSync(script);
        if (!(stats.mode & parseInt('111', 8))) {
            throw new Error(`${script} is not executable`);
        }
    }
});

// Test 5: Check database setup capability
test('Database setup capability', () => {
    try {
        execSync('python -c "from app import app, db; import models; print(\'Database import successful\')"', 
                { stdio: 'pipe', timeout: 10000 });
    } catch (error) {
        throw new Error('Database setup verification failed');
    }
});

// Test 6: Check environment configuration
test('Environment configuration ready', () => {
    const envVars = ['PORT', 'DATABASE_URL'];
    for (const envVar of envVars) {
        if (!process.env[envVar] && envVar === 'DATABASE_URL') {
            console.log(`⚠️  Warning: ${envVar} not set (expected in production)`);
        }
    }
});

// Summary
console.log('\n📊 VERIFICATION SUMMARY');
console.log('======================');

const passed = allTests.filter(t => t.status === 'PASS').length;
const failed = allTests.filter(t => t.status === 'FAIL').length;

console.log(`✅ Passed: ${passed}`);
console.log(`❌ Failed: ${failed}`);
console.log(`📈 Success Rate: ${Math.round((passed / allTests.length) * 100)}%`);

if (failed === 0) {
    console.log('\n🚀 DEPLOYMENT READY!');
    console.log('The Hebrew AI Call Center CRM is ready for deployment.');
    console.log('Use: npm run build && npm run start');
} else {
    console.log('\n⚠️  ISSUES FOUND');
    console.log('Please resolve the failed tests before deployment.');
}

process.exit(failed > 0 ? 1 : 0);