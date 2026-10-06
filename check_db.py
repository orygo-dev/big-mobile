#!/usr/bin/env python3
"""Quick DB diagnostic script"""
import requests

BASE_URL = "https://big-deploy.preview.emergentagent.com/api"

# Login as admin
response = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@demo.com",
    "password": "admin123"
})

if response.status_code == 200:
    token = response.json()["token"]
    print("✅ Admin login successful")
    
    # Get all accounts
    response = requests.get(f"{BASE_URL}/akun?limit=1000", 
                           headers={"Authorization": f"Bearer {token}"})
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n📊 Response type: {type(data)}")
        print(f"Response: {data}")
        
        if isinstance(data, list):
            accounts = data
        elif isinstance(data, dict) and "items" in data:
            accounts = data["items"]
        else:
            print(f"❌ Unexpected response format")
            accounts = []
        
        print(f"\n📊 Total accounts: {len(accounts)}")
        
        if len(accounts) > 0:
            # Count by status
            status_counts = {}
            for acc in accounts:
                if isinstance(acc, dict):
                    status = acc.get("status", "UNKNOWN")
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            print("\n📈 Accounts by status:")
            for status, count in sorted(status_counts.items()):
                print(f"  {status}: {count}")
            
            # Show first few accounts
            print("\n📋 Sample accounts:")
            for acc in accounts[:5]:
                if isinstance(acc, dict):
                    print(f"  - {acc.get('id', 'N/A')[:20]}... | {acc.get('nomor_kontrak', 'N/A')} | {acc.get('nama_debitur', 'N/A')} | Status: {acc.get('status', 'N/A')}")
    else:
        print(f"❌ Failed to get accounts: {response.status_code}")
        print(response.text)
else:
    print(f"❌ Login failed: {response.status_code}")
    print(response.text)
