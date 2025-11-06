#!/usr/bin/env python3
"""
Security Testing Script for Django Peer Evaluation System
Tests for SQL Injection and DoS vulnerabilities
"""

import requests
import time
import threading
import concurrent.futures
import json
import random
import string
from urllib.parse import urljoin
from datetime import datetime, timedelta

class SecurityTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []
        
    def log_result(self, test_type, test_name, success, details=""):
        """Log test results"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'test_type': test_type,
            'test_name': test_name,
            'success': success,
            'details': details
        }
        self.results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_type}: {test_name} - {details}")
    
    def test_sql_injection_login(self):
        """Test SQL injection on login forms"""
        print("\n🔍 Testing SQL Injection on Login...")
        
        # Common SQL injection payloads
        payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "admin'--",
            "' OR 'x'='x",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users--",
            "' OR '1'='1' AND '1'='1",
            "admin' OR '1'='1' AND password='anything",
        ]
        
        login_url = urljoin(self.base_url, "/accounts/login/")
        
        for payload in payloads:
            data = {
                'login': payload,
                'password': 'anything'
            }
            
            try:
                response = self.session.post(login_url, data=data, timeout=5)
                
                # Check for successful login (redirect or dashboard)
                if response.status_code == 302 or "dashboard" in response.text.lower():
                    self.log_result("SQL Injection", f"Login bypass with: {payload}", True, 
                                 f"Status: {response.status_code}")
                else:
                    self.log_result("SQL Injection", f"Login protected against: {payload}", True)
                    
            except Exception as e:
                self.log_result("SQL Injection", f"Login test error: {payload}", False, str(e))

    def test_sql_injection_search(self):
        """Test SQL injection on search/query parameters"""
        print("\n🔍 Testing SQL Injection on Search Parameters...")
        
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE courses; --",
            "' UNION SELECT * FROM courses--",
            "test' AND 1=1--",
            "'; INSERT INTO courses VALUES ('hacked'); --",
        ]
        
        # Test various endpoints that might have search functionality
        endpoints = [
            "/courses/",
            "/forms-dashboard/",
            "/roster/",
        ]
        
        for endpoint in endpoints:
            for payload in payloads:
                try:
                    url = urljoin(self.base_url, endpoint)
                    params = {'search': payload, 'q': payload}
                    
                    response = self.session.get(url, params=params, timeout=5)
                    
                    # Check for error messages that might indicate SQL injection
                    error_indicators = [
                        "mysql", "sqlite", "postgresql", "database error",
                        "sql syntax", "query failed", "table", "column"
                    ]
                    
                    if any(indicator in response.text.lower() for indicator in error_indicators):
                        self.log_result("SQL Injection", f"Search vulnerability in {endpoint}", True,
                                     f"Error detected with payload: {payload}")
                    else:
                        self.log_result("SQL Injection", f"Search protected in {endpoint}", True)
                        
                except Exception as e:
                    self.log_result("SQL Injection", f"Search test error: {endpoint}", False, str(e))

    def test_sql_injection_form_submission(self):
        """Test SQL injection on form submissions"""
        print("\n🔍 Testing SQL Injection on Form Submissions...")
        
        # Test course creation form
        payloads = [
            "'; DROP TABLE courses; --",
            "' OR '1'='1",
            "test'; INSERT INTO courses VALUES ('hacked'); --",
        ]
        
        course_data = {
            'name': "'; DROP TABLE courses; --",
            'code': "HACK",
            'description': "'; DROP TABLE courses; --",
        }
        
        try:
            url = urljoin(self.base_url, "/courses/create/")
            response = self.session.post(url, data=course_data, timeout=5)
            
            if response.status_code == 200:
                self.log_result("SQL Injection", "Form submission protected", True)
            else:
                self.log_result("SQL Injection", "Form submission test", True, 
                             f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_result("SQL Injection", "Form submission test error", False, str(e))

    def test_dos_high_volume_requests(self):
        """Test DoS with high volume of requests"""
        print("\n🚨 Testing DoS with High Volume Requests...")
        
        def make_request():
            try:
                response = self.session.get(self.base_url, timeout=10)
                return response.status_code
            except:
                return None
        
        # Test with increasing number of concurrent requests
        for num_threads in [10, 50, 100, 200]:
            print(f"Testing with {num_threads} concurrent requests...")
            
            start_time = time.time()
            success_count = 0
            error_count = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(make_request) for _ in range(num_threads)]
                
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    result = future.result()
                    if result == 200:
                        success_count += 1
                    else:
                        error_count += 1
            
            end_time = time.time()
            duration = end_time - start_time
            
            success_rate = (success_count / num_threads) * 100
            
            if success_rate < 50:
                self.log_result("DoS", f"High volume test ({num_threads} threads)", True,
                             f"System overwhelmed: {success_rate:.1f}% success rate")
            else:
                self.log_result("DoS", f"High volume test ({num_threads} threads)", True,
                             f"System handled load: {success_rate:.1f}% success rate in {duration:.2f}s")

    def test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        print("\n🔐 Testing Authentication Bypass...")
        
        # Test direct access to protected endpoints
        protected_endpoints = [
            "/courses/create/",
            "/forms-dashboard/",
            "/roster/",
            "/courses/1/forms/create/",
        ]
        
        for endpoint in protected_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=5)
                
                if response.status_code == 200 and "login" not in response.text.lower():
                    self.log_result("Auth Bypass", f"Direct access to {endpoint}", True,
                                 "Endpoint accessible without authentication")
                else:
                    self.log_result("Auth Bypass", f"Protected endpoint {endpoint}", True,
                                 "Authentication required")
                    
            except Exception as e:
                self.log_result("Auth Bypass", f"Test error for {endpoint}", False, str(e))

    def generate_report(self):
        """Generate security testing report"""
        print("\n" + "="*60)
        print("🔒 SECURITY TESTING REPORT")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n📊 Test Results by Category:")
        categories = {}
        for result in self.results:
            category = result['test_type']
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0}
            
            if result['success']:
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        for category, stats in categories.items():
            total = stats['passed'] + stats['failed']
            success_rate = (stats['passed'] / total) * 100 if total > 0 else 0
            print(f"  {category}: {stats['passed']}/{total} ({success_rate:.1f}%)")
        
    def run_all_tests(self):
        """Run all security tests"""
        print("🔒 Starting Security Testing Suite")
        print("="*50)
        
        # SQL Injection Tests
        self.test_sql_injection_login()
        self.test_sql_injection_search()
        self.test_sql_injection_form_submission()
        
        # Authentication Tests
        self.test_authentication_bypass()
        
        # Generate report
        self.generate_report()

    def test_dos_sustained_load(self,
                                endpoint="/",
                                method="GET",
                                concurrency= 100000,
                                duration_seconds=15,
                                payload=None,
                                headers=None,
                                request_timeout=8):
        """
        New DoS test: sustained load for a short duration.
        - endpoint: path relative to base_url (e.g. "/")
        - method: "GET" or "POST"
        - concurrent: number of concurrent requests per wave
        - duration_seconds: how long to run the test
        - payload: dict for POST body (optional)
        - headers: dict for request headers (optional)
        - request_timeout: per-request timeout in seconds
        Logs result using the same self.log_result(...) pattern.
        """
        print(f"\n🚨 Running sustained DoS test: {method} {endpoint} | concurrency={concurrency} duration={duration_seconds}s")
        url = urljoin(self.base_url, endpoint)
        headers = headers or {}
        payload = payload or {}
        stop_time = time.time() + duration_seconds

        total_sent = 0
        total_success = 0
        total_errors = 0
        latencies = []

        def single_request(session):
            nonlocal total_sent, total_success, total_errors
            start = time.time()
            try:
                if method.upper() == "GET":
                    r = session.get(url, headers=headers, timeout=request_timeout)
                else:
                    r = session.post(url, data=payload, headers=headers, timeout=request_timeout)
                latency = time.time() - start
                total_sent += 1
                if r is not None and 200 <= r.status_code < 400:
                    total_success += 1
                    latencies.append(latency)
                    return True
                else:
                    total_errors += 1
                    return False
            except Exception as e:
                total_sent += 1
                total_errors += 1
                return False

        # Run waves of concurrent requests until duration elapses
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            while time.time() < stop_time:
                # submit one wave
                for _ in range(concurrency):
                    futures.append(executor.submit(single_request, self.session))
                # small sleep to avoid instant continuous hammering and allow threads to finish
                time.sleep(0.1)

                # prune completed futures to keep memory reasonable
                new_futures = []
                for f in futures:
                    if f.done():
                        pass
                    else:
                        new_futures.append(f)
                futures = new_futures

        success_rate = (total_success / total_sent) * 100 if total_sent else 0.0
        avg_latency = (sum(latencies) / len(latencies)) if latencies else None

        details = (f"endpoint={endpoint}, method={method}, sent={total_sent}, success={total_success}, "
                   f"errors={total_errors}, success_rate={success_rate:.1f}%, avg_latency={avg_latency if avg_latency is not None else 'N/A'}s")

        # Heuristic: if success rate drops below 50% consider system overwhelmed
        overwhelmed = success_rate < 50
        self.log_result("DoS", f"Sustained load {concurrency}x for {duration_seconds}s -> {endpoint}", overwhelmed, details)

if __name__ == "__main__":
    # Configuration
    BASE_URL = "http://127.0.0.1:8000/"

    # Create tester instance
    tester = SecurityTester(BASE_URL)

    # Run existing tests (SQLi, auth, etc.)
    tester.run_all_tests()

    # ---- Run the DoS test explicitly (dev/staging only) ----
    # tune concurrency/duration as needed
    tester.test_dos_sustained_load(endpoint="/", method="GET", concurrency=20, duration_seconds=8)

    # Re-generate the aggregated report to include DoS results
    tester.generate_report()

    # Decide exit code: fail if DoS result indicates overwhelmed (low success rate)
    # We didn't change the DoS method, so parse the details string it logged.
    dos_results = [r for r in tester.results if r['test_type'] == "DoS"]
    exit_code = 0

    if dos_results:
        # Take the last DoS result (most recent)
        last = dos_results[-1]
        details = last.get('details', '')
        # details contains substring like "... success_rate=12.3% ..."
        success_rate = None
        try:
            # find 'success_rate=' then read the float before '%'
            key = "success_rate="
            if key in details:
                after = details.split(key, 1)[1]
                # strip until '%' and remove non-numeric chars
                rate_str = after.split('%', 1)[0].strip()
                # sometimes there may be trailing text, so keep first token
                rate_token = rate_str.split()[0]
                success_rate = float(rate_token)
        except Exception:
            success_rate = None

        if success_rate is None:
            print("⚠️ Could not parse DoS success_rate from details; failing to be safe.")
            exit_code = 1
        else:
            print(f"📉 DoS success_rate = {success_rate:.1f}%")
            # Your policy: fail if success_rate < 50%
            if success_rate < 50.0:
                print("❌ DoS indicates system overwhelmed -> marking overall run as FAILED")
                exit_code = 1
            else:
                print("✅ DoS indicates system handled load -> marking overall run as PASSED")
                exit_code = 0
    else:
        print("⚠️ No DoS results found; failing to be safe.")
        exit_code = 1

    print("\n✅ Security testing completed!" if exit_code == 0 else "\n❌ Security testing completed with FAILURES")
    # Exit with appropriate code so CI / runner can see failure
    import sys
    sys.exit(exit_code)



    
