#!/usr/bin/env python3
"""Check WordPress API endpoints and authentication methods."""

import requests
from requests.auth import HTTPBasicAuth
import json
import base64

# Site details
site_url = "https://www.welcomebonushunter.com"
username = "admin_6797"
password = "yYI7tCjG28CZZvIg0*"

print("=" * 60)
print("WordPress API Endpoint Check")
print("=" * 60)

# 1. Check if REST API is available
print("\n1. Checking REST API availability...")
try:
    response = requests.get(f"{site_url}/wp-json/", timeout=10)
    if response.status_code == 200:
        print("[SUCCESS] REST API is available")
        data = response.json()
        
        # Show available namespaces
        namespaces = data.get('namespaces', [])
        print(f"\nAvailable namespaces ({len(namespaces)}):")
        for ns in namespaces:
            print(f"  - {ns}")
            
        # Check authentication info
        auth_info = data.get('authentication', {})
        if auth_info:
            print(f"\nAuthentication info: {auth_info}")
            
        # Look for form-related routes
        print("\n2. Checking for form-related endpoints...")
        routes = data.get('routes', {})
        form_endpoints = []
        for route, details in routes.items():
            if any(keyword in route.lower() for keyword in ['form', 'contact', 'sweep', 'lead', 'submission', 'entry']):
                form_endpoints.append(route)
                
        if form_endpoints:
            print(f"Found {len(form_endpoints)} potential form endpoints:")
            for endpoint in form_endpoints[:10]:  # Show first 10
                print(f"  - {endpoint}")
        else:
            print("No obvious form endpoints found in public routes")
            
    else:
        print(f"[ERROR] REST API returned status {response.status_code}")
        
except Exception as e:
    print(f"[ERROR] Failed to access REST API: {e}")

# 2. Test Basic Authentication
print("\n3. Testing Basic Authentication...")
try:
    response = requests.get(
        f"{site_url}/wp-json/wp/v2/users/me",
        auth=HTTPBasicAuth(username, password),
        timeout=10
    )
    if response.status_code == 200:
        print("[SUCCESS] Basic auth successful")
        user_data = response.json()
        print(f"Logged in as: {user_data.get('name', 'Unknown')}")
    else:
        print(f"[FAILED] Basic auth failed with status {response.status_code}")
        if response.status_code == 401:
            print("Note: Basic auth might be disabled. Try Application Passwords.")
            
except Exception as e:
    print(f"[ERROR] Basic auth test failed: {e}")

# 3. Test Application Password format
print("\n4. Testing Application Password format...")
try:
    # Application passwords use base64 encoding
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode('ascii')
    headers = {'Authorization': f'Basic {credentials}'}
    
    response = requests.get(
        f"{site_url}/wp-json/wp/v2/users/me",
        headers=headers,
        timeout=10
    )
    if response.status_code == 200:
        print("[SUCCESS] Application password auth successful")
        user_data = response.json()
        print(f"Logged in as: {user_data.get('name', 'Unknown')}")
    else:
        print(f"[FAILED] Application password auth failed with status {response.status_code}")
        
except Exception as e:
    print(f"[ERROR] Application password test failed: {e}")

# 4. Check for specific form plugin endpoints
print("\n5. Checking for specific form plugin endpoints...")
form_plugins = {
    'Contact Form 7': '/wp-json/contact-form-7/v1',
    'Flamingo': '/wp-json/flamingo/v1',
    'WPForms': '/wp-json/wpforms/v1',
    'Gravity Forms': '/wp-json/gf/v2',
    'Formidable': '/wp-json/frm/v2',
    'Ninja Forms': '/wp-json/ninja-forms/v1',
}

for plugin, endpoint in form_plugins.items():
    try:
        response = requests.get(
            f"{site_url}{endpoint}",
            auth=HTTPBasicAuth(username, password),
            timeout=5
        )
        if response.status_code == 200:
            print(f"[FOUND] {plugin} API is available at {endpoint}")
        elif response.status_code == 401:
            print(f"[AUTH REQUIRED] {plugin} API exists but requires authentication")
        elif response.status_code == 404:
            pass  # Plugin not installed
        else:
            print(f"[STATUS {response.status_code}] {plugin} at {endpoint}")
    except:
        pass  # Plugin not available

# 5. Check for custom endpoints (common patterns)
print("\n6. Checking for custom endpoints...")
custom_endpoints = [
    '/wp-json/custom/v1/leads',
    '/wp-json/api/v1/forms',
    '/wp-json/sweep/v1/rewards',
    '/wp-json/signups/v1',
    '/wp-admin/admin-ajax.php',
]

for endpoint in custom_endpoints:
    try:
        response = requests.get(
            f"{site_url}{endpoint}",
            auth=HTTPBasicAuth(username, password),
            timeout=5
        )
        if response.status_code != 404:
            print(f"[FOUND] Endpoint exists: {endpoint} (Status: {response.status_code})")
    except:
        pass

print("\n" + "=" * 60)
print("Check complete. Review the results above.")
print("=" * 60)