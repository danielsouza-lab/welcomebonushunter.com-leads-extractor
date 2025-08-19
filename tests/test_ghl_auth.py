#!/usr/bin/env python3
"""Debug GHL API authentication."""

import requests
import json
from datetime import datetime

# Your credentials
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJsb2NhdGlvbl9pZCI6IlVoT2c3V0NTckFUcThYYWo0TGxxIiwidmVyc2lvbiI6MSwiaWF0IjoxNzU1NTcxMzI5ODAyLCJzdWIiOiJqZEhQTFBvQVI3cWxJSXBudzUybCJ9.Yy_oZL1jDVuEMe20JiuYdt0pNWLvzHExGsYyAxarstA"
location_id = "UhOg7WCSrATq8Xaj4Llq"

print("=" * 60)
print("GHL API AUTHENTICATION DEBUG")
print("=" * 60)

# Decode JWT token to see its contents (without verification)
import base64

def decode_jwt(token):
    """Decode JWT token without verification to see contents."""
    try:
        # Split token
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None

# Decode and display token info
print("\nToken Analysis:")
payload = decode_jwt(access_token)
if payload:
    print(f"  Location ID in token: {payload.get('location_id')}")
    print(f"  Subject: {payload.get('sub')}")
    print(f"  Version: {payload.get('version')}")
    
    # Check token timestamp
    if 'iat' in payload:
        iat_timestamp = payload['iat']
        # GHL uses milliseconds, convert to seconds
        if iat_timestamp > 10000000000:
            iat_timestamp = iat_timestamp / 1000
        issued_at = datetime.fromtimestamp(iat_timestamp)
        print(f"  Issued at: {issued_at}")
        
        # Check if token might be expired (assuming 90 day expiry)
        days_old = (datetime.now() - issued_at).days
        print(f"  Token age: {days_old} days")
        if days_old > 90:
            print("  [WARNING] Token might be expired (>90 days old)")

print(f"\nProvided Location ID: {location_id}")
if payload and payload.get('location_id') == location_id:
    print("[OK] Location ID matches token")
else:
    print("[WARNING] Location ID mismatch")

print("\n" + "-" * 60)
print("Testing Different API Endpoints:")
print("-" * 60)

# Test different endpoints and auth methods
endpoints = [
    ("https://services.leadconnectorhq.com/locations/" + location_id, "GET"),
    ("https://rest.gohighlevel.com/v1/contacts/", "GET"),
    ("https://services.leadconnectorhq.com/contacts/", "GET"),
]

headers_options = [
    {"Authorization": f"Bearer {access_token}", "Version": "2021-07-28"},
    {"Authorization": f"Bearer {access_token}"},
    {"Authorization": access_token},
]

for endpoint, method in endpoints:
    print(f"\nTesting: {endpoint}")
    for i, headers in enumerate(headers_options, 1):
        try:
            if method == "GET":
                params = {"locationId": location_id} if "contacts" in endpoint else {}
                response = requests.get(endpoint, headers=headers, params=params, timeout=5)
            else:
                response = requests.request(method, endpoint, headers=headers, timeout=5)
            
            print(f"  Attempt {i}: Status {response.status_code}")
            
            if response.status_code == 200:
                print(f"    [SUCCESS] This header format works!")
                print(f"    Headers used: {headers}")
                break
            elif response.status_code == 401:
                error_msg = response.text[:100] if response.text else "No error message"
                print(f"    Auth failed: {error_msg}")
            elif response.status_code == 403:
                print(f"    Forbidden - might need different permissions")
            else:
                print(f"    Response: {response.text[:100] if response.text else 'No response body'}")
                
        except Exception as e:
            print(f"    Error: {str(e)[:50]}")

print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)

print("""
If all attempts failed with 401:
1. The token might be expired - generate a new one in GHL
2. The token might be for a different environment (staging vs production)
3. The API version might be wrong

To generate a new token:
1. Log into Go High Level
2. Go to Settings → Integrations → API
3. Delete the old token if it exists
4. Generate a new API key
5. Copy it immediately (you won't see it again)

Make sure you're in the correct sub-account (location) when generating the token.
""")