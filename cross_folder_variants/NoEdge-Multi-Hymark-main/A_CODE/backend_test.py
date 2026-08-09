#!/usr/bin/env python3
"""
Smart Assessor Backend API Testing Suite
Tests all backend endpoints using the public URL
"""

import requests
import json
import sys
import os
import tempfile
from datetime import datetime
from pathlib import Path

class SmartAssessorAPITester:
    def __init__(self, base_url="https://rubric-engine-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.rubric_id = None
        self.assessment_id = None

    def log_result(self, test_name, success, response_data=None, error_msg=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "response": response_data,
            "error": error_msg
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")
        if error_msg:
            print(f"   Error: {error_msg}")
        if response_data:
            print(f"   Response: {response_data}")

    def run_test(self, test_name, method, endpoint, expected_status=200, data=None, files=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=timeout)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, timeout=timeout)
                elif data:
                    if isinstance(data, dict):
                        response = requests.post(url, json=data, timeout=timeout)
                    else:
                        response = requests.post(url, data=data, timeout=timeout)
                else:
                    response = requests.post(url, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            success = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text[:200]}
            
            error_msg = None if success else f"Expected {expected_status}, got {response.status_code}"
            
            self.log_result(test_name, success, response_data, error_msg)
            return success, response_data

        except Exception as e:
            self.log_result(test_name, False, None, str(e))
            return False, {}

    def create_test_docx(self):
        """Create a simple test DOCX file content for rubric upload"""
        content = """
        Essay Assessment Rubric
        
        Total Marks: 50
        
        Criteria:
        1. Thesis Statement (10 marks)
           - Excellent (8-10): Clear, focused thesis
           - Good (6-7): Adequate thesis
           - Satisfactory (4-5): Basic thesis
           - Needs Improvement (0-3): Weak or missing thesis
        
        2. Evidence (15 marks)
           - Excellent (12-15): Strong, relevant evidence
           - Good (9-11): Good evidence
           - Satisfactory (6-8): Basic evidence
           - Needs Improvement (0-5): Poor evidence
        
        3. Analysis (15 marks)
           - Excellent (12-15): Insightful analysis
           - Good (9-11): Good analysis
           - Satisfactory (6-8): Basic analysis
           - Needs Improvement (0-5): Poor analysis
        
        4. Structure (5 marks)
           - Excellent (4-5): Well organized
           - Good (3): Generally organized
           - Satisfactory (2): Basic organization
           - Needs Improvement (0-1): Poor organization
        
        5. Writing (5 marks)
           - Excellent (4-5): Clear writing
           - Good (3): Generally clear
           - Satisfactory (2): Adequate writing
           - Needs Improvement (0-1): Poor writing
        """
        return content

    def create_test_essay(self):
        """Create a test essay for assessment"""
        essay = """
        The Impact of Technology on Modern Education
        
        Introduction:
        Technology has revolutionized many aspects of human life, and education is no exception. This essay argues that while technology has brought significant benefits to modern education, it also presents challenges that educators must carefully navigate to maximize its potential.
        
        Body Paragraph 1 - Benefits:
        One of the most significant advantages of technology in education is increased accessibility. Online learning platforms have made education available to students regardless of geographical location or physical limitations. For instance, students in remote areas can now access the same quality of education as those in urban centers through virtual classrooms and digital resources.
        
        Body Paragraph 2 - Enhanced Learning:
        Technology has also transformed how students learn and engage with content. Interactive multimedia presentations, educational games, and simulation software make learning more engaging and help students understand complex concepts more effectively. Research shows that students retain information better when they can interact with the material rather than passively consuming it.
        
        Body Paragraph 3 - Challenges:
        However, technology in education is not without its drawbacks. The digital divide means that not all students have equal access to technological resources, potentially widening educational inequalities. Additionally, over-reliance on technology may reduce face-to-face interaction and critical thinking skills if not properly balanced with traditional teaching methods.
        
        Conclusion:
        In conclusion, technology has fundamentally changed modern education for the better, offering unprecedented opportunities for learning and accessibility. While challenges exist, they can be overcome through thoughtful implementation and ensuring equitable access to technological resources. The future of education lies in finding the right balance between technological innovation and traditional pedagogical approaches.
        """
        return essay

    def test_health_check(self):
        """Test GET /api/health"""
        return self.run_test("Health Check", "GET", "/api/health")

    def test_create_default_rubric(self):
        """Test POST /api/rubric/essay-default"""
        data = {
            "name": "Test Essay Rubric",
            "total_marks": 50
        }
        success, response = self.run_test(
            "Create Default Essay Rubric", 
            "POST", 
            "/api/rubric/essay-default",
            expected_status=200,
            data=data
        )
        
        if success and response.get('success') and response.get('rubric', {}).get('_id'):
            self.rubric_id = response['rubric']['_id']
            print(f"   Created rubric ID: {self.rubric_id}")
        
        return success

    def test_upload_rubric(self):
        """Test POST /api/rubric/upload with a text file as rubric"""
        # Create a temporary text file to simulate rubric upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False) as f:
            f.write(self.create_test_docx())
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                files = {'file': ('test_rubric.docx', f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                data = {'name': 'Uploaded Test Rubric'}
                
                success, response = self.run_test(
                    "Upload Rubric File",
                    "POST",
                    "/api/rubric/upload",
                    expected_status=200,
                    data=data,
                    files=files
                )
                
                if success and response.get('success') and not self.rubric_id:
                    rubric_data = response.get('rubric', {})
                    if rubric_data.get('_id'):
                        self.rubric_id = rubric_data['_id']
                        print(f"   Uploaded rubric ID: {self.rubric_id}")
                
                return success
        finally:
            os.unlink(temp_path)

    def test_list_rubrics(self):
        """Test GET /api/rubrics"""
        success, response = self.run_test("List All Rubrics", "GET", "/api/rubrics")
        
        if success:
            rubrics = response.get('rubrics', [])
            print(f"   Found {len(rubrics)} rubrics")
            if len(rubrics) > 0 and not self.rubric_id:
                self.rubric_id = rubrics[0]['_id']
                print(f"   Using first rubric ID: {self.rubric_id}")
        
        return success

    def test_get_rubric(self):
        """Test GET /api/rubric/{rubric_id}"""
        if not self.rubric_id:
            self.log_result("Get Specific Rubric", False, None, "No rubric_id available")
            return False
        
        return self.run_test("Get Specific Rubric", "GET", f"/api/rubric/{self.rubric_id}")

    def test_single_assessment(self):
        """Test POST /api/assess/single"""
        if not self.rubric_id:
            self.log_result("Single Assessment", False, None, "No rubric_id available")
            return False

        # Create a temporary text file as essay
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(self.create_test_essay())
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                files = {'file': ('test_essay.txt', f, 'text/plain')}
                data = {
                    'rubric_id': self.rubric_id,
                    'student_id': 'TEST_STUDENT_001'
                }
                
                success, response = self.run_test(
                    "Single Essay Assessment",
                    "POST",
                    "/api/assess/single",
                    expected_status=200,
                    data=data,
                    files=files,
                    timeout=60  # AI assessment might take longer
                )
                
                if success and response.get('_id'):
                    self.assessment_id = response['_id']
                    print(f"   Assessment ID: {self.assessment_id}")
                    print(f"   Score: {response.get('total_score', 0)}/{response.get('max_score', 100)}")
                    print(f"   Percentage: {response.get('percentage', 0)}%")
                
                return success
        finally:
            os.unlink(temp_path)

    def test_list_assessments(self):
        """Test GET /api/assessments"""
        success, response = self.run_test("List Recent Assessments", "GET", "/api/assessments")
        
        if success:
            assessments = response.get('assessments', [])
            print(f"   Found {len(assessments)} assessments")
            if len(assessments) > 0 and not self.assessment_id:
                self.assessment_id = assessments[0]['_id']
                print(f"   Using first assessment ID: {self.assessment_id}")
        
        return success

    def test_get_assessment(self):
        """Test GET /api/assessment/{assessment_id}"""
        if not self.assessment_id:
            self.log_result("Get Specific Assessment", False, None, "No assessment_id available")
            return False
        
        success, response = self.run_test("Get Assessment Details", "GET", f"/api/assessment/{self.assessment_id}")
        
        if success:
            print(f"   Student: {response.get('student_id', 'N/A')}")
            print(f"   Score: {response.get('total_score', 0)}/{response.get('max_score', 100)}")
            if response.get('overall_feedback'):
                print(f"   Feedback: {response['overall_feedback'][:100]}...")
        
        return success

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print("=" * 60)
        print("SMART ASSESSOR API TESTING SUITE")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print()

        # Basic health check
        self.test_health_check()
        
        # Rubric tests
        self.test_create_default_rubric()
        self.test_upload_rubric() 
        self.test_list_rubrics()
        self.test_get_rubric()
        
        # Assessment tests (requires rubric)
        self.test_single_assessment()
        self.test_list_assessments()
        self.test_get_assessment()
        
        # Final results
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Return summary
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": self.tests_run - self.tests_passed,
            "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0,
            "test_details": self.test_results
        }

def main():
    tester = SmartAssessorAPITester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results["failed_tests"] == 0 else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()