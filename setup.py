#!/usr/bin/env python
"""
Setup script for EagleOps project.
This script installs dependencies and sets up the project.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Main setup function."""
    print("Setting up EagleOps project...")
    
    # Get the project directory
    project_dir = Path(__file__).resolve().parent
    
    # Install dependencies
    print("\n=== Installing dependencies ===")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", 
                          os.path.join(project_dir, "requirements.txt"), "--use-pep517"])
    
    # Run migrations
    print("\n=== Running migrations ===")
    subprocess.check_call([sys.executable, os.path.join(project_dir, "manage.py"), "migrate"])
    
    # Ask if user wants to create a superuser
    create_superuser = input("\nDo you want to create a superuser? (y/n): ")
    if create_superuser.lower() == 'y':
        subprocess.check_call([sys.executable, os.path.join(project_dir, "manage.py"), "createsuperuser"])
    
    # Run the setup_oauth command explicitly
    print("\n=== Setting up OAuth ===")
    subprocess.check_call([sys.executable, os.path.join(project_dir, "manage.py"), "setup_oauth"])
    
    print("\n=== Setup complete! ===")
    print("You can now run the server with:")
    print(f"python {os.path.join(project_dir, 'manage.py')} runserver")

if __name__ == "__main__":
    main() 