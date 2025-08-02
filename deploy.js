#!/usr/bin/env node
/**
 * Hebrew AI Call Center CRM - Deployment Bridge Script
 * סקריפט גשר לפריסת מערכת CRM מוקד שיחות AI בעברית
 * 
 * This script serves as a bridge between Node.js deployment expectations
 * and the actual Python Flask application.
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🚀 Hebrew AI Call Center CRM - Deployment Bridge');
console.log('==================================================');

// Build phase
function build() {
    console.log('📦 Starting build process...');
    
    try {
        // Install Python dependencies
        console.log('🐍 Installing Python dependencies...');
        execSync('python -m pip install --upgrade pip', { stdio: 'inherit' });
        execSync('python -m pip install .', { stdio: 'inherit' });
        
        // Create necessary directories
        console.log('📁 Creating directories...');
        const dirs = [
            'static/voice_responses',
            'logs',
            'docs/backups',
            'baileys_auth_info'
        ];
        dirs.forEach(dir => {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
                console.log(`✅ Created directory: ${dir}`);
            }
        });
        
        // Setup database
        console.log('🗄️ Setting up database...');
        execSync(`python -c "
from app import app, db
import models
try:
    import crm_models
except:
    pass

with app.app_context():
    try:
        db.create_all()
        print('✅ Database tables created successfully')
    except Exception as e:
        print(f'⚠️ Database setup warning: {e}')
"`, { stdio: 'inherit' });
        
        console.log('✅ Build completed successfully!');
        return true;
        
    } catch (error) {
        console.error('❌ Build failed:', error.message);
        return false;
    }
}

// Start phase
function start() {
    console.log('🚀 Starting Hebrew AI Call Center CRM...');
    
    // Set environment variables
    process.env.FLASK_ENV = 'production';
    process.env.FLASK_DEBUG = 'false';
    process.env.PYTHONPATH = '.';
    
    const port = process.env.PORT || 5000;
    const host = process.env.HOST || '0.0.0.0';
    
    console.log(`📍 Starting on ${host}:${port}`);
    console.log(`🕐 ${new Date().toISOString()}`);
    
    // Start Python Flask application
    const pythonProcess = spawn('python', ['main.py'], {
        stdio: 'inherit',
        env: { ...process.env }
    });
    
    pythonProcess.on('error', (error) => {
        console.error('❌ Failed to start Python application:', error);
        process.exit(1);
    });
    
    pythonProcess.on('exit', (code) => {
        console.log(`Python application exited with code ${code}`);
        process.exit(code);
    });
    
    // Handle graceful shutdown
    process.on('SIGTERM', () => {
        console.log('🛑 Received SIGTERM, shutting down gracefully...');
        pythonProcess.kill('SIGTERM');
    });
    
    process.on('SIGINT', () => {
        console.log('🛑 Received SIGINT, shutting down gracefully...');
        pythonProcess.kill('SIGINT');
    });
}

// Main execution
const command = process.argv[2];

switch (command) {
    case 'build':
        const buildSuccess = build();
        process.exit(buildSuccess ? 0 : 1);
        break;
    case 'start':
        start();
        break;
    default:
        console.log('Usage: node deploy.js [build|start]');
        console.log('  build - Prepare the application for production');
        console.log('  start - Start the production server');
        process.exit(1);
}