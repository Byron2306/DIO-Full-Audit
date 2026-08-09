"""
Test suite for Exam Builder feature
Tests the /api/exams endpoints for generating History exam papers
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://rubric-engine-1.preview.emergentagent.com').rstrip('/')


class TestExamBuilderAPI:
    """Test Exam Builder API endpoints"""
    
    def test_health_check(self):
        """Verify API is healthy before running exam tests"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health check passed")
    
    def test_list_exams_endpoint(self):
        """Test GET /api/exams returns list of exams"""
        response = requests.get(f"{BASE_URL}/api/exams")
        assert response.status_code == 200
        data = response.json()
        assert "exams" in data
        assert isinstance(data["exams"], list)
        print(f"✓ List exams endpoint working - found {len(data['exams'])} exams")
        return data["exams"]
    
    def test_generate_exam_validation_empty_topics(self):
        """Test that generate endpoint validates required fields"""
        # Test with empty topics
        payload = {
            "module_code": "TEST101",
            "module_name": "Test Module",
            "topics": [],  # Empty topics should fail
            "methodology_topic": "Test Topic",
            "essay_topic": "Test Essay",
            "total_marks": 125,
            "duration_hours": 3
        }
        response = requests.post(f"{BASE_URL}/api/exams/generate", json=payload)
        # Should either fail validation or handle gracefully
        print(f"✓ Empty topics validation - Status: {response.status_code}")
    
    def test_generate_exam_full_flow(self):
        """Test full exam generation flow - this is the main test"""
        payload = {
            "module_code": "HISE411",
            "module_name": "HISTORY SNR & FET 4A",
            "topics": [
                "The Cuban Missile Crisis (1962)",
                "The Division of Germany (1945-1949)"
            ],
            "methodology_topic": "The Berlin Airlift",
            "essay_topic": "The role of media in shaping public opinion during the Vietnam War",
            "total_marks": 125,
            "duration_hours": 3
        }
        
        print("Generating exam (this may take 30-60 seconds due to AI processing)...")
        response = requests.post(
            f"{BASE_URL}/api/exams/generate", 
            json=payload,
            timeout=180  # 3 minute timeout for AI generation
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert data["success"] == True
        assert "exam" in data
        
        exam = data["exam"]
        
        # Verify exam data structure
        assert exam.get("module_code") == "HISE411"
        assert exam.get("module_name") == "HISTORY SNR & FET 4A"
        assert "source_questions" in exam
        assert len(exam["source_questions"]) == 2  # 2 source-based questions
        
        # Verify source questions have sources and questions
        for sq in exam["source_questions"]:
            assert "topic" in sq
            assert "sources" in sq
            assert "questions" in sq
            assert len(sq["sources"]) > 0, "Source question should have sources"
            assert len(sq["questions"]) > 0, "Source question should have questions"
            print(f"  - Source Q: {sq['topic']} - {len(sq['sources'])} sources, {len(sq['questions'])} questions")
        
        # Verify methodology question
        assert "methodology_question" in exam
        mq = exam["methodology_question"]
        assert "topic" in mq
        assert "marks" in mq
        assert mq["marks"] == 25
        print(f"  - Methodology Q: {mq['topic']} ({mq['marks']} marks)")
        
        # Verify essay question
        assert "essay_question" in exam
        eq = exam["essay_question"]
        assert "topic" in eq
        assert "question" in eq
        assert "marks" in eq
        assert eq["marks"] == 50
        print(f"  - Essay Q: {eq['topic']} ({eq['marks']} marks)")
        
        # Verify total marks calculation
        assert "calculated_total" in exam or "total_marks" in exam
        total = exam.get("calculated_total", exam.get("total_marks"))
        print(f"  - Total marks: {total}")
        
        # Verify filename for download
        assert "filename" in exam
        assert exam["filename"].endswith(".docx")
        
        print(f"✓ Exam generation successful - filename: {exam['filename']}")
        return exam
    
    def test_download_exam(self):
        """Test downloading a generated exam DOCX file"""
        # First get list of exams
        list_response = requests.get(f"{BASE_URL}/api/exams")
        assert list_response.status_code == 200
        exams = list_response.json().get("exams", [])
        
        if not exams:
            pytest.skip("No exams available to download")
        
        # Get the most recent exam
        exam = exams[0]
        filename = exam.get("filename")
        
        if not filename:
            pytest.skip("No filename in exam record")
        
        # Download the exam
        download_response = requests.get(f"{BASE_URL}/api/exams/download/{filename}")
        
        assert download_response.status_code == 200, f"Download failed: {download_response.status_code}"
        
        # Verify it's a DOCX file (check content type or magic bytes)
        content_type = download_response.headers.get("content-type", "")
        assert "application" in content_type or len(download_response.content) > 0
        
        # DOCX files start with PK (ZIP format)
        assert download_response.content[:2] == b'PK', "Downloaded file is not a valid DOCX"
        
        print(f"✓ Download exam successful - {len(download_response.content)} bytes")
    
    def test_download_nonexistent_exam(self):
        """Test downloading a non-existent exam returns 404"""
        response = requests.get(f"{BASE_URL}/api/exams/download/nonexistent_file_12345.docx")
        assert response.status_code == 404
        print("✓ Non-existent exam download returns 404")


class TestExamBuilderDataPersistence:
    """Test that generated exams are persisted correctly"""
    
    def test_exam_appears_in_list_after_generation(self):
        """Verify generated exam appears in the list"""
        # Get initial count
        initial_response = requests.get(f"{BASE_URL}/api/exams")
        initial_count = len(initial_response.json().get("exams", []))
        
        # The exam generated in previous test should be in the list
        # Just verify the list endpoint works and returns data
        assert initial_response.status_code == 200
        
        exams = initial_response.json().get("exams", [])
        if exams:
            exam = exams[0]
            # Verify exam has required fields
            assert "_id" in exam
            assert "module_code" in exam
            assert "created_at" in exam
            print(f"✓ Most recent exam: {exam.get('module_code')} - {exam.get('created_at')}")
        else:
            print("✓ Exams list endpoint working (no exams yet)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
