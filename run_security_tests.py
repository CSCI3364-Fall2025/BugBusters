#!/usr/bin/env python3
"""
Quick Security Test Runner
Simplified script to run security tests on your Django application
"""

import subprocess
import sys
import os
from pathlib import Path

def run_security_tests():
    """
    Run the security testing script with proper setup
    """
    print("🔒 Django Security Testing Suite")
    print("=" * 40)
    print("⚠️  WARNING: Only run this on your own systems!")
    print("⚠️  Make sure your Django server is running on http://127.0.0.1:8000/")
    print("=" * 40)
    
    # Check if Django server is running
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ Django server is running")
        else:
            print("❌ Django server not responding properly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Django server: {e}")
        print("💡 Start your Django server with: python manage.py runserver")
        return False
    
    # Run the security testing script
    try:
        print("\n🚀 Starting security tests...")
        result = subprocess.run([
            sys.executable, 
            "sqli_testing_script.py"
        ], capture_output=True, text=True, timeout=300)
        
        print("📊 Test Results:")
        print(result.stdout)
        
        if result.stderr:
            print("⚠️  Warnings/Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Security tests completed successfully")
        else:
            print(f"❌ Security tests failed with return code: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Security tests timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error running security tests: {e}")
        return False

def main():
    """
    Main function to run all security tests
    """
    print("🔒 Django Security Testing Suite")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("sqli_testing_script.py"):
        print("❌ Security testing script not found!")
        print("💡 Make sure you're in the correct directory")
        return False
    
    # Run security tests
    print("\n1. Running Security Vulnerability Tests...")
    security_success = run_security_tests()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SECURITY TESTING SUMMARY")
    print("=" * 50)
    
    if security_success:
        print("✅ Security vulnerability tests: PASSED")
    else:
        print("❌ Security vulnerability tests: FAILED")
    
    return security_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
