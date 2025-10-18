#!/usr/bin/env python3
"""
Setup script for AgentLocator deployment.
Installs Python dependencies and Node.js dependencies for Baileys WhatsApp service.
"""

import os
import subprocess
import sys
from setuptools import setup, find_packages
from setuptools.command.install import install

class PostInstallCommand(install):
    """Post-installation hook to install Node.js dependencies"""
    def run(self):
        # Run the default install
        install.run(self)
        
        # Install Baileys dependencies
        baileys_dir = os.path.join(os.path.dirname(__file__), 'services', 'whatsapp')
        if os.path.exists(baileys_dir):
            print("📦 Installing Baileys Node.js dependencies...")
            try:
                subprocess.check_call(
                    ['npm', 'install', '--omit=dev', '--prefer-offline', '--no-audit', '--no-fund'],
                    cwd=baileys_dir,
                    stdout=sys.stdout,
                    stderr=sys.stderr
                )
                print("✅ Baileys dependencies installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Failed to install Baileys dependencies: {e}")
                print("Baileys may not work properly until dependencies are installed")
        else:
            print(f"⚠️ Baileys directory not found at {baileys_dir}")

# Read requirements from requirements.txt
requirements = []
requirements_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
if os.path.exists(requirements_file):
    with open(requirements_file, 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='agentlocator',
    version='1.0.0',
    description='Hebrew CRM system for real estate businesses with AI-powered assistant',
    author='AgentLocator Team',
    packages=find_packages(where='server'),
    package_dir={'': 'server'},
    install_requires=requirements,
    cmdclass={
        'install': PostInstallCommand,
    },
    python_requires='>=3.11',
)
