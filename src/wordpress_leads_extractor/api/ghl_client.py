"""Go High Level API Client for lead synchronization."""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GHLClient:
    """Client for Go High Level API v2."""
    
    def __init__(
        self,
        access_token: str,
        location_id: str,
        api_version: str = "2021-07-28",
        base_url: str = "https://rest.gohighlevel.com/v1"
    ):
        """
        Initialize GHL API client.
        
        Args:
            access_token: OAuth 2.0 access token or API key
            location_id: Sub-account/Location ID
            api_version: API version to use
            base_url: Base URL for GHL API
        """
        self.access_token = access_token
        self.location_id = location_id
        self.api_version = api_version
        self.base_url = base_url
        
        # Set up session with retry logic
        self.session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504)
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Version": api_version,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def create_contact(
        self,
        email: str,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new contact in GHL.
        
        Args:
            email: Contact email address
            phone: Contact phone number
            first_name: Contact first name
            last_name: Contact last name
            name: Full name (if first/last not provided)
            tags: List of tags to apply
            custom_fields: Dictionary of custom field values
            source: Lead source
            
        Returns:
            Dictionary containing API response
        """
        # Build request payload
        payload = {
            "locationId": self.location_id,
            "email": email
        }
        
        if phone:
            payload["phone"] = phone
            
        if first_name:
            payload["firstName"] = first_name
        elif name:
            # Try to split name if first/last not provided
            name_parts = name.strip().split(" ", 1)
            payload["firstName"] = name_parts[0]
            if len(name_parts) > 1:
                payload["lastName"] = name_parts[1]
                
        if last_name:
            payload["lastName"] = last_name
            
        if tags:
            payload["tags"] = tags
            
        if custom_fields:
            payload["customField"] = custom_fields
            
        if source:
            payload["source"] = source
        else:
            payload["source"] = "WordPress Lead Form"
        
        # Make API request
        url = f"{self.base_url}/contacts/"
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            # Build response dict
            result = {
                "request_timestamp": datetime.utcnow().isoformat(),
                "request_body": payload,
                "response_status_code": response.status_code,
                "response_body": None,
                "response_timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error_message": None,
                "ghl_contact_id": None
            }
            
            # Try to parse response
            try:
                response_data = response.json()
                result["response_body"] = response_data
            except json.JSONDecodeError:
                result["response_body"] = {"raw_text": response.text}
            
            # Handle different response codes
            if response.status_code == 200 or response.status_code == 201:
                result["success"] = True
                # Extract contact ID from response
                if isinstance(result["response_body"], dict):
                    result["ghl_contact_id"] = result["response_body"].get("contact", {}).get("id") or \
                                              result["response_body"].get("id")
                logger.info(f"Successfully created contact: {email}")
                
            elif response.status_code == 422:
                # Validation error or duplicate
                result["error_message"] = "Validation error or duplicate contact"
                if isinstance(result["response_body"], dict):
                    # Check if it's a duplicate
                    if "duplicate" in str(result["response_body"]).lower():
                        result["error_message"] = "Duplicate contact"
                        # Sometimes GHL returns the existing contact ID
                        existing_id = result["response_body"].get("contact", {}).get("id")
                        if existing_id:
                            result["ghl_contact_id"] = existing_id
                            result["success"] = True  # Consider duplicate as success
                            
            elif response.status_code == 401:
                result["error_message"] = "Authentication failed - check access token"
                
            elif response.status_code == 400:
                result["error_message"] = "Bad request - check payload format"
                
            else:
                result["error_message"] = f"API error: {response.status_code}"
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {email}: {str(e)}")
            return {
                "request_timestamp": datetime.utcnow().isoformat(),
                "request_body": payload,
                "response_status_code": None,
                "response_body": None,
                "response_timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error_message": str(e),
                "ghl_contact_id": None
            }
    
    def update_contact(
        self,
        contact_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing contact in GHL.
        
        Args:
            contact_id: GHL contact ID
            email: Updated email
            phone: Updated phone
            first_name: Updated first name
            last_name: Updated last name
            tags: Tags to add
            custom_fields: Custom fields to update
            
        Returns:
            Dictionary containing API response
        """
        payload = {}
        
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone
        if first_name:
            payload["firstName"] = first_name
        if last_name:
            payload["lastName"] = last_name
        if tags:
            payload["tags"] = tags
        if custom_fields:
            payload["customField"] = custom_fields
            
        url = f"{self.base_url}/contacts/{contact_id}"
        
        try:
            response = self.session.put(url, json=payload, timeout=30)
            
            result = {
                "request_timestamp": datetime.utcnow().isoformat(),
                "request_body": payload,
                "response_status_code": response.status_code,
                "response_body": None,
                "response_timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error_message": None
            }
            
            try:
                result["response_body"] = response.json()
            except json.JSONDecodeError:
                result["response_body"] = {"raw_text": response.text}
            
            if response.status_code == 200:
                result["success"] = True
                logger.info(f"Successfully updated contact: {contact_id}")
            else:
                result["error_message"] = f"Update failed: {response.status_code}"
                
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Update request failed for {contact_id}: {str(e)}")
            return {
                "request_timestamp": datetime.utcnow().isoformat(),
                "request_body": payload,
                "response_status_code": None,
                "response_body": None,
                "response_timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error_message": str(e)
            }
    
    def get_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Search for a contact by email.
        
        Args:
            email: Email to search for
            
        Returns:
            Contact data if found, None otherwise
        """
        url = f"{self.base_url}/contacts/"
        params = {
            "locationId": self.location_id,
            "query": email,
            "limit": 1
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                contacts = data.get("contacts", [])
                if contacts:
                    # Verify email matches exactly
                    for contact in contacts:
                        if contact.get("email", "").lower() == email.lower():
                            return contact
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Search failed for {email}: {str(e)}")
            return None
    
    def add_tag_to_contact(self, contact_id: str, tag: str) -> bool:
        """
        Add a tag to an existing contact.
        
        Args:
            contact_id: GHL contact ID
            tag: Tag to add
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/contacts/{contact_id}/tags"
        payload = {"tags": [tag]}
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to add tag to {contact_id}: {str(e)}")
            return False
    
    def create_or_update_contact(
        self,
        email: str,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new contact or update if exists.
        
        Args:
            email: Contact email
            phone: Contact phone
            first_name: First name
            last_name: Last name
            name: Full name
            tags: Tags to apply
            custom_fields: Custom field values
            source: Lead source
            
        Returns:
            Dictionary containing API response
        """
        # First try to create
        result = self.create_contact(
            email=email,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            name=name,
            tags=tags,
            custom_fields=custom_fields,
            source=source
        )
        
        # If duplicate, try to find and update
        if not result["success"] and "duplicate" in str(result.get("error_message", "")).lower():
            existing = self.get_contact_by_email(email)
            if existing:
                contact_id = existing.get("id")
                if contact_id:
                    # Update existing contact
                    update_result = self.update_contact(
                        contact_id=contact_id,
                        phone=phone,
                        first_name=first_name,
                        last_name=last_name,
                        tags=tags,
                        custom_fields=custom_fields
                    )
                    update_result["ghl_contact_id"] = contact_id
                    update_result["note"] = "Updated existing contact"
                    return update_result
        
        return result
    
    def test_connection(self) -> bool:
        """
        Test API connection and authentication.
        
        Returns:
            True if connection successful
        """
        url = f"{self.base_url}/locations/{self.location_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                logger.info("GHL API connection successful")
                return True
            else:
                logger.error(f"GHL API connection failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"GHL API connection error: {str(e)}")
            return False