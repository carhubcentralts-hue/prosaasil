import subprocess
import os
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop


class BuildFrontendCommand:
    """Custom command to build frontend during installation"""
    
    def run_build(self):
        """Build the frontend"""
        client_dir = os.path.join(os.path.dirname(__file__), 'client')
        dist_dir = os.path.join(client_dir, 'dist')
        
        print("\n" + "="*80)
        print("🔨 Building Frontend for Production Deployment")
        print("="*80)
        
        # Always rebuild for fresh deployment
        if os.path.exists(dist_dir):
            print(f"⚠️ Removing old build: {dist_dir}")
            import shutil
            shutil.rmtree(dist_dir)
        
        print(f"📂 Working directory: {client_dir}")
        
        # Install frontend dependencies
        print("\n📦 Installing frontend dependencies...")
        subprocess.check_call(['npm', 'install'], cwd=client_dir)
        
        # Build frontend
        print("\n🏗️ Building frontend with Vite...")
        subprocess.check_call(['npm', 'run', 'build'], cwd=client_dir)
        
        # Verify build
        index_html = os.path.join(dist_dir, 'index.html')
        if os.path.exists(index_html):
            print("\n✅ Frontend build complete!")
            print(f"✅ Verified: {index_html}")
            
            # Show build files
            assets_dir = os.path.join(dist_dir, 'assets')
            if os.path.exists(assets_dir):
                files = os.listdir(assets_dir)
                print(f"📦 Built {len(files)} asset files")
                for f in files[:5]:
                    print(f"   - {f}")
        else:
            print("\n❌ Build verification failed - index.html not found")
            raise RuntimeError("Frontend build failed")
        
        print("="*80 + "\n")


class PostInstallCommand(install, BuildFrontendCommand):
    """Post-installation for installation mode"""
    def run(self):
        self.run_build()
        install.run(self)


class PostDevelopCommand(develop, BuildFrontendCommand):
    """Post-installation for development mode"""
    def run(self):
        self.run_build()
        develop.run(self)


setup(
    name="agentlocator",
    version="1.0.0",
    description="AI-powered CRM for Hebrew real estate businesses",
    packages=find_packages(where=".", include=["server*"]),
    install_requires=[
        "asgiref>=3.10.0",
        "eventlet>=0.40.3",
        "flask>=3.1.2",
        "flask-bcrypt>=1.0.1",
        "flask-cors>=6.0.1",
        "flask-login>=0.6.3",
        "flask-seasurf>=2.0.0",
        "flask-sqlalchemy>=3.1.1",
        "google-cloud-speech>=2.33.0",
        "google-cloud-texttospeech>=2.31.0",
        "honcho>=2.0.0",
        "hypercorn>=0.17.3",
        "numpy>=2.3.4",
        "openai>=2.2.0",
        "psycopg2-binary>=2.9.10",
        "pyjwt>=2.10.1",
        "reportlab>=4.4.4",
        "requests>=2.32.5",
        "scipy>=1.16.2",
        "sqlalchemy>=2.0.43",
        "starlette>=0.48.0",
        "twilio>=9.8.3",
        "uvicorn[standard]>=0.37.0",
    ],
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
    python_requires=">=3.11",
)
