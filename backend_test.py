#!/usr/bin/env python3
"""
Backend API Test for FieldCollector Assignment Workflow
Tests the refactored 1 Assignment = 1 Unit = 1 Officer = 1 Letter business rule
"""

import requests
import json
import sys
from typing import Dict, Optional

# Configuration
BASE_URL = "https://big-deploy.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "admin123"
PETUGAS_A_EMAIL = "petugas@demo.com"
PETUGAS_A_PASSWORD = "petugas123"
PETUGAS_B_EMAIL = "siti@demo.com"
PETUGAS_B_PASSWORD = "petugas123"

# Test state
test_state = {
    "admin_token": None,
    "petugas_a_token": None,
    "petugas_a_id": None,
    "petugas_b_token": None,
    "petugas_b_id": None,
    "unit1_id": None,
    "assignment_id": None,
    "letter_id": None,
    "document_number": None,
    "assignment_number": None,
}

# Test results
test_results = []


class TestResult:
    def __init__(self, name: str, passed: bool, details: str = ""):
        self.name = name
        self.passed = passed
        self.details = details


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    result = TestResult(name, passed, details)
    test_results.append(result)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {name}")
    if details:
        print(f"  Details: {details}")


def make_request(method: str, endpoint: str, token: Optional[str] = None, 
                 json_data: Optional[Dict] = None, data: Optional[Dict] = None,
                 files: Optional[Dict] = None) -> requests.Response:
    """Make HTTP request with proper headers"""
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            if data is not None:
                # For multipart/form-data, let requests set Content-Type automatically
                response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
            else:
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=json_data, timeout=30)
        elif method == "PATCH":
            headers["Content-Type"] = "application/json"
            response = requests.patch(url, headers=headers, json=json_data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except Exception as e:
        print(f"Request error: {e}")
        raise


def test_1_login():
    """Test 1: LOGIN - Admin and both Petugas"""
    print("\n" + "="*80)
    print("TEST 1: LOGIN")
    print("="*80)
    
    # Login Admin
    try:
        response = make_request("POST", "/auth/login", json_data={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            test_state["admin_token"] = data.get("token")
            log_test("1.1 Admin Login", True, f"Token received, user: {data.get('user', {}).get('email')}")
        else:
            log_test("1.1 Admin Login", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("1.1 Admin Login", False, f"Exception: {str(e)}")
        return False
    
    # Login Petugas A
    try:
        response = make_request("POST", "/auth/login", json_data={
            "email": PETUGAS_A_EMAIL,
            "password": PETUGAS_A_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            test_state["petugas_a_token"] = data.get("token")
            test_state["petugas_a_id"] = data.get("user", {}).get("id")
            log_test("1.2 Petugas A Login", True, f"Token received, ID: {test_state['petugas_a_id']}")
        else:
            log_test("1.2 Petugas A Login", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("1.2 Petugas A Login", False, f"Exception: {str(e)}")
        return False
    
    # Login Petugas B
    try:
        response = make_request("POST", "/auth/login", json_data={
            "email": PETUGAS_B_EMAIL,
            "password": PETUGAS_B_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            test_state["petugas_b_token"] = data.get("token")
            test_state["petugas_b_id"] = data.get("user", {}).get("id")
            log_test("1.3 Petugas B Login", True, f"Token received, ID: {test_state['petugas_b_id']}")
        else:
            log_test("1.3 Petugas B Login", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("1.3 Petugas B Login", False, f"Exception: {str(e)}")
        return False
    
    return True


def test_2_get_available_unit():
    """Test 2: GET AVAILABLE UNIT - Get unassigned account"""
    print("\n" + "="*80)
    print("TEST 2: GET AVAILABLE UNIT")
    print("="*80)
    
    try:
        response = make_request("GET", "/akun?status=BELUM_DITUGASKAN&limit=1000", 
                               token=test_state["admin_token"])
        
        if response.status_code == 200:
            data = response.json()
            # Handle both list and paginated response formats
            if isinstance(data, list):
                accounts = data
            elif isinstance(data, dict) and "items" in data:
                accounts = data["items"]
            else:
                accounts = []
            
            if len(accounts) > 0:
                test_state["unit1_id"] = accounts[0].get("id")
                log_test("2.1 Get Available Unit", True, 
                        f"Found {len(accounts)} unassigned units, selected: {test_state['unit1_id']}")
                return True
            else:
                log_test("2.1 Get Available Unit", False, "No unassigned units found")
                return False
        else:
            log_test("2.1 Get Available Unit", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("2.1 Get Available Unit", False, f"Exception: {str(e)}")
        return False


def test_3_create_assignment():
    """Test 3: CREATE ASSIGNMENT - Create assignment with auto letter"""
    print("\n" + "="*80)
    print("TEST 3: CREATE ASSIGNMENT")
    print("="*80)
    
    # Create assignment
    try:
        response = make_request("POST", "/penugasan", 
                               token=test_state["admin_token"],
                               json_data={
                                   "petugas_id": test_state["petugas_a_id"],
                                   "account_id": test_state["unit1_id"],
                                   "valid_from": "2025-07-01",
                                   "valid_until": "2025-12-31",
                                   "catatan": "test tugas"
                               })
        
        if response.status_code == 200:
            data = response.json()
            test_state["letter_id"] = data.get("id")
            test_state["assignment_id"] = data.get("assignment_id")
            test_state["assignment_number"] = data.get("assignment_number")
            test_state["document_number"] = data.get("document_number")
            
            # Verify all required fields
            has_id = data.get("id") is not None
            has_assignment_id = data.get("assignment_id") is not None
            has_assignment_number = data.get("assignment_number") is not None
            has_document_number = data.get("document_number") is not None
            
            if has_id and has_assignment_id and has_assignment_number and has_document_number:
                log_test("3.1 Create Assignment", True, 
                        f"Letter ID: {test_state['letter_id']}, Assignment ID: {test_state['assignment_id']}, "
                        f"Assignment #: {test_state['assignment_number']}, Doc #: {test_state['document_number']}")
            else:
                log_test("3.1 Create Assignment", False, 
                        f"Missing fields - id:{has_id}, assignment_id:{has_assignment_id}, "
                        f"assignment_number:{has_assignment_number}, document_number:{has_document_number}")
                return False
        else:
            log_test("3.1 Create Assignment", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("3.1 Create Assignment", False, f"Exception: {str(e)}")
        return False
    
    # Verify letter exists in list
    try:
        response = make_request("GET", "/surat-tugas", token=test_state["admin_token"])
        
        if response.status_code == 200:
            letters = response.json()
            found = any(l.get("id") == test_state["letter_id"] for l in letters)
            if found:
                log_test("3.2 Verify Letter in List", True, "Letter found in surat-tugas list")
            else:
                log_test("3.2 Verify Letter in List", False, "Letter not found in list")
                return False
        else:
            log_test("3.2 Verify Letter in List", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("3.2 Verify Letter in List", False, f"Exception: {str(e)}")
        return False
    
    # Verify document is auto-finalized
    try:
        response = make_request("GET", f"/surat-tugas/{test_state['letter_id']}/document", 
                               token=test_state["admin_token"])
        
        if response.status_code == 200:
            doc_data = response.json()
            is_finalized = doc_data.get("is_finalized") == True
            has_doc_number = doc_data.get("data", {}).get("letter", {}).get("document_number") is not None
            doc_status = doc_data.get("document_status")
            
            if is_finalized and has_doc_number and doc_status == "ACTIVE":
                log_test("3.3 Verify Auto-Finalized", True, 
                        f"Document is finalized with status {doc_status}, doc_number present")
            else:
                log_test("3.3 Verify Auto-Finalized", False, 
                        f"is_finalized:{is_finalized}, has_doc_number:{has_doc_number}, status:{doc_status}")
                return False
        else:
            log_test("3.3 Verify Auto-Finalized", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("3.3 Verify Auto-Finalized", False, f"Exception: {str(e)}")
        return False
    
    # Verify account status changed to DITUGASKAN
    try:
        response = make_request("GET", f"/akun/{test_state['unit1_id']}", 
                               token=test_state["admin_token"])
        
        if response.status_code == 200:
            account = response.json()
            status = account.get("status")
            if status == "DITUGASKAN":
                log_test("3.4 Verify Account Status", True, f"Account status is {status}")
            else:
                log_test("3.4 Verify Account Status", False, f"Expected DITUGASKAN, got {status}")
                return False
        else:
            log_test("3.4 Verify Account Status", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("3.4 Verify Account Status", False, f"Exception: {str(e)}")
        return False
    
    return True


def test_4_duplicate_block():
    """Test 4: DUPLICATE BLOCK - Prevent duplicate active assignment"""
    print("\n" + "="*80)
    print("TEST 4: DUPLICATE ASSIGNMENT BLOCK")
    print("="*80)
    
    try:
        response = make_request("POST", "/penugasan", 
                               token=test_state["admin_token"],
                               json_data={
                                   "petugas_id": test_state["petugas_b_id"],  # Different petugas
                                   "account_id": test_state["unit1_id"],  # Same unit
                                   "valid_from": "2025-07-01",
                                   "valid_until": "2025-12-31",
                                   "catatan": "duplicate test"
                               })
        
        if response.status_code == 400:
            error_msg = response.json().get("detail", "")
            log_test("4.1 Duplicate Assignment Block", True, 
                    f"Correctly blocked with 400: {error_msg}")
            return True
        else:
            log_test("4.1 Duplicate Assignment Block", False, 
                    f"Expected 400, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("4.1 Duplicate Assignment Block", False, f"Exception: {str(e)}")
        return False


def test_5_officer_visibility():
    """Test 5: OFFICER VISIBILITY - Task isolation between officers"""
    print("\n" + "="*80)
    print("TEST 5: OFFICER VISIBILITY")
    print("="*80)
    
    # Petugas A should see the task
    try:
        response = make_request("GET", "/my/tugas", token=test_state["petugas_a_token"])
        
        if response.status_code == 200:
            tasks = response.json()
            found = any(t.get("account", {}).get("id") == test_state["unit1_id"] for t in tasks)
            
            if found:
                task = next(t for t in tasks if t.get("account", {}).get("id") == test_state["unit1_id"])
                has_assignment_id = task.get("assignment_id") is not None
                has_letter_id = task.get("letter_id") is not None
                has_letter_nomor = task.get("letter_nomor") is not None
                
                if has_assignment_id and has_letter_id and has_letter_nomor:
                    log_test("5.1 Petugas A Sees Task", True, 
                            f"Task visible with assignment_id:{task.get('assignment_id')}, "
                            f"letter_id:{task.get('letter_id')}, letter_nomor:{task.get('letter_nomor')}")
                else:
                    log_test("5.1 Petugas A Sees Task", False, 
                            f"Task found but missing fields - assignment_id:{has_assignment_id}, "
                            f"letter_id:{has_letter_id}, letter_nomor:{has_letter_nomor}")
                    return False
            else:
                log_test("5.1 Petugas A Sees Task", False, "Task not found in Petugas A's task list")
                return False
        else:
            log_test("5.1 Petugas A Sees Task", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("5.1 Petugas A Sees Task", False, f"Exception: {str(e)}")
        return False
    
    # Petugas B should NOT see the task
    try:
        response = make_request("GET", "/my/tugas", token=test_state["petugas_b_token"])
        
        if response.status_code == 200:
            tasks = response.json()
            found = any(t.get("account", {}).get("id") == test_state["unit1_id"] for t in tasks)
            
            if not found:
                log_test("5.2 Petugas B Does NOT See Task", True, 
                        "Task correctly isolated - not visible to Petugas B")
            else:
                log_test("5.2 Petugas B Does NOT See Task", False, 
                        "Task incorrectly visible to Petugas B (isolation broken)")
                return False
        else:
            log_test("5.2 Petugas B Does NOT See Task", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("5.2 Petugas B Does NOT See Task", False, f"Exception: {str(e)}")
        return False
    
    return True


def test_6_task_detail():
    """Test 6: TASK DETAIL - Get task detail with assignment_id"""
    print("\n" + "="*80)
    print("TEST 6: TASK DETAIL")
    print("="*80)
    
    try:
        response = make_request("GET", f"/my/tugas/{test_state['unit1_id']}", 
                               token=test_state["petugas_a_token"])
        
        if response.status_code == 200:
            detail = response.json()
            has_assignment_id = detail.get("assignment_id") is not None
            existing_report = detail.get("existing_report")
            
            if has_assignment_id and existing_report is None:
                log_test("6.1 Get Task Detail", True, 
                        f"Task detail retrieved with assignment_id:{detail.get('assignment_id')}, "
                        f"existing_report is null")
            else:
                log_test("6.1 Get Task Detail", False, 
                        f"has_assignment_id:{has_assignment_id}, existing_report:{existing_report}")
                return False
        else:
            log_test("6.1 Get Task Detail", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("6.1 Get Task Detail", False, f"Exception: {str(e)}")
        return False
    
    return True


def test_7_submit_report():
    """Test 7: SUBMIT REPORT - Submit report with assignment_id"""
    print("\n" + "="*80)
    print("TEST 7: SUBMIT REPORT")
    print("="*80)
    
    # Submit report
    try:
        response = make_request("POST", "/laporan", 
                               token=test_state["petugas_a_token"],
                               data={
                                   "assignment_id": test_state["assignment_id"],
                                   "account_id": test_state["unit1_id"],
                                   "status": "TIDAK_DITEMUKAN",
                                   "catatan": "Unit tidak ditemukan di alamat yang tercatat dalam sistem",
                                   "lokasi_alasan": "GPS ditolak user"
                               })
        
        if response.status_code == 200:
            report = response.json()
            report_assignment_id = report.get("assignment_id")
            report_account_id = report.get("account_id")
            
            if report_assignment_id == test_state["assignment_id"] and report_account_id == test_state["unit1_id"]:
                log_test("7.1 Submit Report", True, 
                        f"Report created with assignment_id:{report_assignment_id}, "
                        f"account_id:{report_account_id}")
            else:
                log_test("7.1 Submit Report", False, 
                        f"Mismatch - expected assignment_id:{test_state['assignment_id']}, "
                        f"got:{report_assignment_id}")
                return False
        else:
            log_test("7.1 Submit Report", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("7.1 Submit Report", False, f"Exception: {str(e)}")
        return False
    
    # Verify sudah_dilaporkan flag
    try:
        response = make_request("GET", "/my/tugas", token=test_state["petugas_a_token"])
        
        if response.status_code == 200:
            tasks = response.json()
            task = next((t for t in tasks if t.get("account", {}).get("id") == test_state["unit1_id"]), None)
            
            if task and task.get("sudah_dilaporkan") == True:
                log_test("7.2 Verify sudah_dilaporkan Flag", True, "Flag correctly set to true")
            else:
                log_test("7.2 Verify sudah_dilaporkan Flag", False, 
                        f"Flag not set correctly: {task.get('sudah_dilaporkan') if task else 'task not found'}")
                return False
        else:
            log_test("7.2 Verify sudah_dilaporkan Flag", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("7.2 Verify sudah_dilaporkan Flag", False, f"Exception: {str(e)}")
        return False
    
    # Try to submit duplicate report (should fail)
    try:
        response = make_request("POST", "/laporan", 
                               token=test_state["petugas_a_token"],
                               data={
                                   "assignment_id": test_state["assignment_id"],
                                   "account_id": test_state["unit1_id"],
                                   "status": "TIDAK_DITEMUKAN",
                                   "catatan": "Duplicate report test - should fail",
                                   "lokasi_alasan": "GPS ditolak user"
                               })
        
        if response.status_code == 400:
            log_test("7.3 Duplicate Report Block", True, 
                    f"Duplicate report correctly blocked with 400: {response.json().get('detail', '')}")
        else:
            log_test("7.3 Duplicate Report Block", False, 
                    f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        log_test("7.3 Duplicate Report Block", False, f"Exception: {str(e)}")
        return False
    
    return True


def test_8_cancel_reassign():
    """Test 8: CANCEL + REASSIGN - Cancel assignment and reassign"""
    print("\n" + "="*80)
    print("TEST 8: CANCEL + REASSIGN")
    print("="*80)
    
    # Get a fresh unassigned unit for this test
    try:
        response = make_request("GET", "/akun?status=BELUM_DITUGASKAN&limit=1000", 
                               token=test_state["admin_token"])
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("items", data) if isinstance(data, dict) else data
            if len(accounts) > 0:
                fresh_unit_id = accounts[0].get("id")
                print(f"  Using fresh unit: {fresh_unit_id}")
            else:
                log_test("8.0 Get Fresh Unit", False, "No unassigned units available")
                return False
        else:
            log_test("8.0 Get Fresh Unit", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("8.0 Get Fresh Unit", False, f"Exception: {str(e)}")
        return False
    
    # Create a new assignment for the fresh unit
    try:
        response = make_request("POST", "/penugasan", 
                               token=test_state["admin_token"],
                               json_data={
                                   "petugas_id": test_state["petugas_a_id"],
                                   "account_id": fresh_unit_id,
                                   "valid_from": "2025-07-01",
                                   "valid_until": "2025-12-31",
                                   "catatan": "test for cancellation"
                               })
        
        if response.status_code == 200:
            data = response.json()
            cancel_test_letter_id = data.get("id")
            print(f"  Created assignment letter: {cancel_test_letter_id}")
        else:
            log_test("8.0 Create Assignment for Cancel Test", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("8.0 Create Assignment for Cancel Test", False, f"Exception: {str(e)}")
        return False
    
    # Cancel the assignment letter
    try:
        response = make_request("PATCH", f"/surat-tugas/{cancel_test_letter_id}/status", 
                               token=test_state["admin_token"],
                               json_data={"status": "dibatalkan"})
        
        if response.status_code == 200:
            log_test("8.1 Cancel Assignment", True, "Assignment letter cancelled successfully")
        else:
            log_test("8.1 Cancel Assignment", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("8.1 Cancel Assignment", False, f"Exception: {str(e)}")
        return False
    
    # Verify account status back to BELUM_DITUGASKAN
    try:
        response = make_request("GET", f"/akun/{fresh_unit_id}", 
                               token=test_state["admin_token"])
        
        if response.status_code == 200:
            account = response.json()
            status = account.get("status")
            if status == "BELUM_DITUGASKAN":
                log_test("8.2 Verify Account Status Reset", True, 
                        f"Account status correctly reset to {status}")
            else:
                log_test("8.2 Verify Account Status Reset", False, 
                        f"Expected BELUM_DITUGASKAN, got {status}")
                return False
        else:
            log_test("8.2 Verify Account Status Reset", False, f"Status {response.status_code}")
            return False
    except Exception as e:
        log_test("8.2 Verify Account Status Reset", False, f"Exception: {str(e)}")
        return False
    
    # Reassign to a different petugas
    try:
        response = make_request("POST", "/penugasan", 
                               token=test_state["admin_token"],
                               json_data={
                                   "petugas_id": test_state["petugas_b_id"],  # Different petugas
                                   "account_id": fresh_unit_id,
                                   "valid_from": "2025-07-01",
                                   "valid_until": "2025-12-31",
                                   "catatan": "reassignment test"
                               })
        
        if response.status_code == 200:
            data = response.json()
            new_assignment_id = data.get("assignment_id")
            new_document_number = data.get("document_number")
            log_test("8.3 Reassign After Cancel", True, 
                    f"Reassignment successful - new assignment_id:{new_assignment_id}, "
                    f"doc_number:{new_document_number}")
        else:
            log_test("8.3 Reassign After Cancel", False, 
                    f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("8.3 Reassign After Cancel", False, f"Exception: {str(e)}")
        return False
    
    return True


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r.passed)
    failed = sum(1 for r in test_results if not r.passed)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n" + "="*80)
        print("FAILED TESTS:")
        print("="*80)
        for r in test_results:
            if not r.passed:
                print(f"\n❌ {r.name}")
                if r.details:
                    print(f"   {r.details}")
    
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("FIELDCOLLECTOR ASSIGNMENT WORKFLOW TEST")
    print("Testing: 1 Assignment = 1 Unit = 1 Officer = 1 Letter")
    print("="*80)
    
    # Run tests in sequence
    if not test_1_login():
        print("\n❌ Login failed - cannot continue")
        print_summary()
        sys.exit(1)
    
    if not test_2_get_available_unit():
        print("\n❌ Cannot get available unit - cannot continue")
        print_summary()
        sys.exit(1)
    
    test_3_create_assignment()
    test_4_duplicate_block()
    test_5_officer_visibility()
    test_6_task_detail()
    test_7_submit_report()
    test_8_cancel_reassign()
    
    # Print summary
    success = print_summary()
    
    if success:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
