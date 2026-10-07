#!/usr/bin/env python3
"""
Backend API Tests for FieldCollector - Branding & File Upload Enhancement
Tests the new branding and file upload endpoints.
"""

import requests
import io
import base64
from pathlib import Path

# Load backend URL from frontend .env
env_path = Path("/app/frontend/.env")
BACKEND_URL = None
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BACKEND_URL = line.split("=", 1)[1].strip()
            break

if not BACKEND_URL:
    raise ValueError("REACT_APP_BACKEND_URL not found in /app/frontend/.env")

API_BASE = f"{BACKEND_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"  Details: {details}")

def create_valid_png():
    """Create a minimal valid 1x1 PNG with proper magic bytes"""
    # Minimal 1x1 transparent PNG (67 bytes)
    png_data = (
        b'\x89PNG\r\n\x1a\n'  # PNG signature
        b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
        b'\r\n-\xb4'
        b'\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return png_data

def create_valid_pdf():
    """Create a minimal valid PDF with proper magic bytes"""
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
197
%%EOF
"""
    return pdf_content

def test_1_public_branding():
    """Test 1: GET /api/branding WITHOUT Authorization header"""
    print("\n=== TEST 1: Public Branding Endpoint ===")
    try:
        response = requests.get(f"{API_BASE}/branding", timeout=10)
        
        if response.status_code != 200:
            log_test("GET /api/branding (public)", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        
        # Check required keys
        required_keys = ["app_name", "logo", "company_name"]
        missing_keys = [k for k in required_keys if k not in data]
        
        if missing_keys:
            log_test("GET /api/branding (public)", False, 
                    f"Missing keys: {missing_keys}. Got: {list(data.keys())}")
            return None
        
        # Verify app_name is string (default "FieldCollector")
        if not isinstance(data["app_name"], str):
            log_test("GET /api/branding (public)", False, 
                    f"app_name should be string, got {type(data['app_name'])}")
            return None
        
        # Verify logo is string (may be empty)
        if not isinstance(data["logo"], str):
            log_test("GET /api/branding (public)", False, 
                    f"logo should be string, got {type(data['logo'])}")
            return None
        
        log_test("GET /api/branding (public)", True, 
                f"app_name={data['app_name']}, logo={'(empty)' if not data['logo'] else '(present)'}, company_name={data['company_name']}")
        return data
        
    except Exception as e:
        log_test("GET /api/branding (public)", False, f"Exception: {str(e)}")
        return None

def test_2_logo_upload(admin_token):
    """Test 2: POST /api/company/logo with valid PNG and negative test"""
    print("\n=== TEST 2: Logo Upload ===")
    
    # Test 2a: Valid PNG upload
    try:
        png_data = create_valid_png()
        files = {"file": ("logo.png", io.BytesIO(png_data), "image/png")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(f"{API_BASE}/company/logo", files=files, headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("POST /api/company/logo (valid PNG)", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return False
        
        company_data = response.json()
        
        # Check that logo field exists and starts with data:image/png;base64,
        if "logo" not in company_data:
            log_test("POST /api/company/logo (valid PNG)", False, 
                    "Response missing 'logo' field")
            return False
        
        if not company_data["logo"].startswith("data:image/png;base64,"):
            log_test("POST /api/company/logo (valid PNG)", False, 
                    f"Logo should start with 'data:image/png;base64,', got: {company_data['logo'][:50]}")
            return False
        
        log_test("POST /api/company/logo (valid PNG)", True, 
                "Logo uploaded successfully, stored as base64 data URL")
        
        # Test 2b: Verify GET /api/branding now shows the logo
        branding_response = requests.get(f"{API_BASE}/branding", timeout=10)
        if branding_response.status_code == 200:
            branding_data = branding_response.json()
            if branding_data.get("logo") and branding_data["logo"].startswith("data:image/png"):
                log_test("GET /api/branding after logo upload", True, 
                        "Logo now appears in public branding endpoint")
            else:
                log_test("GET /api/branding after logo upload", False, 
                        f"Logo not reflected in branding: {branding_data.get('logo', '(missing)')[:50]}")
        
        # Test 2c: NEGATIVE - Upload non-PNG file (text/plain)
        text_data = b"This is not a PNG file"
        files = {"file": ("test.txt", io.BytesIO(text_data), "text/plain")}
        
        response = requests.post(f"{API_BASE}/company/logo", files=files, headers=headers, timeout=10)
        
        if response.status_code == 400:
            log_test("POST /api/company/logo (negative: text/plain)", True, 
                    f"Correctly rejected non-PNG with 400: {response.json().get('detail', '')}")
        else:
            log_test("POST /api/company/logo (negative: text/plain)", False, 
                    f"Expected 400, got {response.status_code}")
        
        return True
        
    except Exception as e:
        log_test("POST /api/company/logo", False, f"Exception: {str(e)}")
        return False

def test_3_app_name(admin_token):
    """Test 3: PUT /api/company to set app_name"""
    print("\n=== TEST 3: App Name Update ===")
    
    try:
        # First, get current company data
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{API_BASE}/company", headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("GET /api/company", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return False
        
        company_data = response.json()
        
        # Update with app_name = "MyBrand"
        company_data["app_name"] = "MyBrand"
        
        response = requests.put(f"{API_BASE}/company", json=company_data, headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("PUT /api/company (app_name=MyBrand)", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return False
        
        updated_data = response.json()
        
        if updated_data.get("app_name") != "MyBrand":
            log_test("PUT /api/company (app_name=MyBrand)", False, 
                    f"app_name not updated. Expected 'MyBrand', got '{updated_data.get('app_name')}'")
            return False
        
        log_test("PUT /api/company (app_name=MyBrand)", True, 
                "app_name successfully updated to 'MyBrand'")
        
        # Verify GET /api/company shows the new app_name
        response = requests.get(f"{API_BASE}/company", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("app_name") == "MyBrand":
                log_test("GET /api/company (verify app_name)", True, 
                        "app_name persisted correctly")
            else:
                log_test("GET /api/company (verify app_name)", False, 
                        f"app_name not persisted. Got: {data.get('app_name')}")
        
        # Verify GET /api/branding shows the new app_name
        response = requests.get(f"{API_BASE}/branding", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("app_name") == "MyBrand":
                log_test("GET /api/branding (verify app_name)", True, 
                        "app_name reflected in public branding")
            else:
                log_test("GET /api/branding (verify app_name)", False, 
                        f"app_name not in branding. Got: {data.get('app_name')}")
        
        return True
        
    except Exception as e:
        log_test("PUT /api/company (app_name)", False, f"Exception: {str(e)}")
        return False

def test_4_sk_pdf_upload(admin_token):
    """Test 4: POST /api/surat-kuasa/{sk_id}/file with PDF"""
    print("\n=== TEST 4: Surat Kuasa PDF Upload ===")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get list of Surat Kuasa to pick an ID
        response = requests.get(f"{API_BASE}/surat-kuasa", headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("GET /api/surat-kuasa", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return None
        
        sk_list = response.json()
        
        if not sk_list:
            log_test("GET /api/surat-kuasa", False, 
                    "No Surat Kuasa found in database. Cannot test PDF upload.")
            return None
        
        sk_id = sk_list[0]["id"]
        log_test("GET /api/surat-kuasa", True, 
                f"Found {len(sk_list)} Surat Kuasa records. Using SK ID: {sk_id}")
        
        # Test 4a: Valid PDF upload
        pdf_data = create_valid_pdf()
        files = {"file": ("surat_kuasa.pdf", io.BytesIO(pdf_data), "application/pdf")}
        
        response = requests.post(f"{API_BASE}/surat-kuasa/{sk_id}/file", 
                                files=files, headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("POST /api/surat-kuasa/{id}/file (valid PDF)", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        
        if "file_url" not in result:
            log_test("POST /api/surat-kuasa/{id}/file (valid PDF)", False, 
                    "Response missing 'file_url' field")
            return None
        
        file_url = result["file_url"]
        
        if not file_url.startswith("/api/files/"):
            log_test("POST /api/surat-kuasa/{id}/file (valid PDF)", False, 
                    f"file_url should start with '/api/files/', got: {file_url}")
            return None
        
        log_test("POST /api/surat-kuasa/{id}/file (valid PDF)", True, 
                f"PDF uploaded successfully. file_url: {file_url}")
        
        # Test 4b: NEGATIVE - Upload non-PDF (text/plain)
        text_data = b"This is not a PDF file"
        files = {"file": ("test.txt", io.BytesIO(text_data), "text/plain")}
        
        response = requests.post(f"{API_BASE}/surat-kuasa/{sk_id}/file", 
                                files=files, headers=headers, timeout=10)
        
        if response.status_code == 400:
            log_test("POST /api/surat-kuasa/{id}/file (negative: text/plain)", True, 
                    f"Correctly rejected non-PDF with 400: {response.json().get('detail', '')}")
        else:
            log_test("POST /api/surat-kuasa/{id}/file (negative: text/plain)", False, 
                    f"Expected 400, got {response.status_code}")
        
        # Test 4c: NEGATIVE - Upload to non-existent SK ID
        fake_sk_id = "00000000-0000-0000-0000-000000000000"
        files = {"file": ("surat_kuasa.pdf", io.BytesIO(pdf_data), "application/pdf")}
        
        response = requests.post(f"{API_BASE}/surat-kuasa/{fake_sk_id}/file", 
                                files=files, headers=headers, timeout=10)
        
        if response.status_code == 404:
            log_test("POST /api/surat-kuasa/{id}/file (negative: non-existent ID)", True, 
                    f"Correctly returned 404 for non-existent SK: {response.json().get('detail', '')}")
        else:
            log_test("POST /api/surat-kuasa/{id}/file (negative: non-existent ID)", False, 
                    f"Expected 404, got {response.status_code}")
        
        return file_url
        
    except Exception as e:
        log_test("POST /api/surat-kuasa/{id}/file", False, f"Exception: {str(e)}")
        return None

def test_5_file_serve_auth(admin_token, file_url):
    """Test 5: GET /api/files/{path} with and without auth"""
    print("\n=== TEST 5: File Serving with Auth ===")
    
    if not file_url:
        log_test("File serving test", False, "No file_url from previous test")
        return False
    
    try:
        # Extract storage path from file_url (strip /api/files/ prefix)
        if not file_url.startswith("/api/files/"):
            log_test("File serving test", False, f"Invalid file_url format: {file_url}")
            return False
        
        storage_path = file_url[len("/api/files/"):]
        
        # Test 5a: GET with auth query parameter
        response = requests.get(f"{API_BASE}/files/{storage_path}?auth={admin_token}", timeout=10)
        
        if response.status_code != 200:
            log_test("GET /api/files/{path}?auth=token", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return False
        
        if response.headers.get("content-type") != "application/pdf":
            log_test("GET /api/files/{path}?auth=token", False, 
                    f"Expected content-type application/pdf, got {response.headers.get('content-type')}")
            return False
        
        if len(response.content) == 0:
            log_test("GET /api/files/{path}?auth=token", False, 
                    "Response body is empty")
            return False
        
        log_test("GET /api/files/{path}?auth=token", True, 
                f"File served successfully with auth. Size: {len(response.content)} bytes, content-type: application/pdf")
        
        # Test 5b: GET without auth (should return 401)
        response = requests.get(f"{API_BASE}/files/{storage_path}", timeout=10)
        
        if response.status_code == 401:
            log_test("GET /api/files/{path} (no auth)", True, 
                    f"Correctly returned 401 without auth: {response.json().get('detail', '')}")
        else:
            log_test("GET /api/files/{path} (no auth)", False, 
                    f"Expected 401, got {response.status_code}")
        
        return True
        
    except Exception as e:
        log_test("File serving test", False, f"Exception: {str(e)}")
        return False

def test_6_enriched_account_list(admin_token):
    """Test 6: GET /api/akun?limit=5 with surat_kuasa_file and petugas_name"""
    print("\n=== TEST 6: Enriched Account List ===")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{API_BASE}/akun?limit=5", headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test("GET /api/akun?limit=5", False, 
                    f"Expected 200, got {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        
        if "items" not in data:
            log_test("GET /api/akun?limit=5", False, 
                    "Response missing 'items' field")
            return False
        
        items = data["items"]
        
        if not items:
            log_test("GET /api/akun?limit=5", True, 
                    "No accounts in database (empty result is valid)")
            return True
        
        # Check that each item has the required enriched fields
        required_fields = ["surat_kuasa_file", "petugas_name"]
        
        for i, item in enumerate(items):
            missing_fields = [f for f in required_fields if f not in item]
            if missing_fields:
                log_test("GET /api/akun?limit=5", False, 
                        f"Item {i} missing fields: {missing_fields}. Keys: {list(item.keys())}")
                return False
        
        # Count how many have non-empty surat_kuasa_file
        with_sk_file = sum(1 for item in items if item.get("surat_kuasa_file"))
        
        log_test("GET /api/akun?limit=5", True, 
                f"Retrieved {len(items)} accounts. All have surat_kuasa_file and petugas_name fields. "
                f"{with_sk_file} accounts have uploaded SK files.")
        
        # Show sample data
        if items:
            sample = items[0]
            print(f"  Sample account: nomor_kontrak={sample.get('nomor_kontrak')}, "
                  f"surat_kuasa_file={'(present)' if sample.get('surat_kuasa_file') else '(empty)'}, "
                  f"petugas_name={sample.get('petugas_name')}")
        
        return True
        
    except Exception as e:
        log_test("GET /api/akun?limit=5", False, f"Exception: {str(e)}")
        return False

def main():
    """Run all tests"""
    print(f"Backend API Tests - Branding & File Upload")
    print(f"Backend URL: {API_BASE}")
    print("=" * 80)
    
    # Login as admin
    print("\n=== Admin Login ===")
    try:
        response = requests.post(f"{API_BASE}/auth/login", 
                                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                                timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Admin login failed: {response.status_code} - {response.text}")
            return
        
        admin_token = response.json()["token"]
        print(f"✅ Admin logged in successfully")
        
    except Exception as e:
        print(f"❌ Admin login exception: {str(e)}")
        return
    
    # Run tests
    test_1_public_branding()
    test_2_logo_upload(admin_token)
    test_3_app_name(admin_token)
    file_url = test_4_sk_pdf_upload(admin_token)
    test_5_file_serve_auth(admin_token, file_url)
    test_6_enriched_account_list(admin_token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for t in test_results if t["passed"])
    total = len(test_results)
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total if total > 0 else 0}%)\n")
    
    # Group by status
    failed_tests = [t for t in test_results if not t["passed"]]
    
    if failed_tests:
        print("FAILED TESTS:")
        for t in failed_tests:
            print(f"  ❌ {t['name']}")
            if t['details']:
                print(f"     {t['details']}")
    else:
        print("✅ ALL TESTS PASSED!")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
