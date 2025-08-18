"""WordPress API client for extracting leads and form submissions."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth
import base64

logger = logging.getLogger(__name__)


class WordPressClient:
    """Client for interacting with WordPress REST API and common form plugins."""
    
    def __init__(self, site_url: str, username: str, password: str, 
                 use_application_password: bool = False):
        """
        Initialize WordPress API client.
        
        Args:
            site_url: WordPress site URL (e.g., https://example.com)
            username: WordPress admin username
            password: WordPress admin password or application password
            use_application_password: Whether to use application passwords (WP 5.6+)
        """
        self.site_url = site_url.rstrip('/')
        self.username = username
        self.password = password
        self.use_application_password = use_application_password
        self.session = requests.Session()
        self._setup_authentication()
        
    def _setup_authentication(self):
        """Set up authentication for API requests."""
        if self.use_application_password:
            # Application passwords use basic auth with base64
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode('ascii')
            self.session.headers['Authorization'] = f'Basic {credentials}'
        else:
            # Standard authentication
            self.session.auth = HTTPBasicAuth(self.username, self.password)
    
    def test_connection(self) -> bool:
        """Test the connection to WordPress API."""
        try:
            response = self.session.get(f"{self.site_url}/wp-json/wp/v2/users/me")
            response.raise_for_status()
            logger.info(f"Successfully connected to WordPress as {response.json().get('name')}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to WordPress: {e}")
            return False
    
    def get_contact_form_7_submissions(self, form_id: Optional[int] = None,
                                      since: Optional[datetime] = None) -> List[Dict]:
        """
        Get Contact Form 7 submissions using Flamingo plugin.
        
        Args:
            form_id: Specific form ID to filter (optional)
            since: Get submissions since this datetime (optional)
            
        Returns:
            List of form submissions
        """
        submissions = []
        
        try:
            # Flamingo stores CF7 submissions
            endpoint = f"{self.site_url}/wp-json/flamingo/v1/inbound"
            params = {"per_page": 100, "page": 1}
            
            if form_id:
                params["channel_id"] = form_id
                
            response = self.session.get(endpoint, params=params)
            
            if response.status_code == 404:
                logger.warning("Flamingo plugin not found. Trying alternative methods...")
                return self._get_cf7_from_database()
                
            response.raise_for_status()
            data = response.json()
            
            for submission in data:
                submission_date = datetime.fromisoformat(submission['date'].replace('Z', '+00:00'))
                if since and submission_date < since:
                    continue
                    
                submissions.append({
                    'id': submission['id'],
                    'form_name': submission.get('channel', 'Unknown'),
                    'date': submission_date,
                    'name': submission.get('from_name', ''),
                    'email': submission.get('from_email', ''),
                    'subject': submission.get('subject', ''),
                    'fields': submission.get('fields', {}),
                    'meta': submission.get('meta', {}),
                    'source': 'contact_form_7'
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching CF7 submissions: {e}")
            
        return submissions
    
    def get_wpforms_submissions(self, form_id: Optional[int] = None,
                               since: Optional[datetime] = None) -> List[Dict]:
        """
        Get WPForms submissions.
        
        Args:
            form_id: Specific form ID to filter (optional)
            since: Get submissions since this datetime (optional)
            
        Returns:
            List of form submissions
        """
        submissions = []
        
        try:
            # WPForms REST API endpoint
            endpoint = f"{self.site_url}/wp-json/wpforms/v1/entries"
            params = {"per_page": 100}
            
            if form_id:
                params["form_id"] = form_id
                
            response = self.session.get(endpoint, params=params)
            
            if response.status_code == 404:
                logger.warning("WPForms API not available")
                return []
                
            response.raise_for_status()
            data = response.json()
            
            for entry in data:
                entry_date = datetime.fromisoformat(entry['date'])
                if since and entry_date < since:
                    continue
                    
                # Parse form fields
                fields = {}
                for field_id, field_value in entry.get('fields', {}).items():
                    fields[field_value.get('name', f'field_{field_id}')] = field_value.get('value', '')
                    
                submissions.append({
                    'id': entry['id'],
                    'form_id': entry['form_id'],
                    'date': entry_date,
                    'fields': fields,
                    'ip': entry.get('ip', ''),
                    'user_agent': entry.get('user_agent', ''),
                    'source': 'wpforms'
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching WPForms submissions: {e}")
            
        return submissions
    
    def get_gravity_forms_entries(self, form_id: Optional[int] = None,
                                 since: Optional[datetime] = None) -> List[Dict]:
        """
        Get Gravity Forms entries.
        
        Args:
            form_id: Specific form ID to filter (optional)
            since: Get submissions since this datetime (optional)
            
        Returns:
            List of form submissions
        """
        submissions = []
        
        try:
            # Gravity Forms REST API v2
            if form_id:
                endpoint = f"{self.site_url}/wp-json/gf/v2/forms/{form_id}/entries"
            else:
                endpoint = f"{self.site_url}/wp-json/gf/v2/entries"
                
            params = {"_per_page": 100}
            
            response = self.session.get(endpoint, params=params)
            
            if response.status_code == 404:
                logger.warning("Gravity Forms API not available")
                return []
                
            response.raise_for_status()
            data = response.json()
            
            for entry in data.get('entries', []):
                entry_date = datetime.fromisoformat(entry['date_created'])
                if since and entry_date < since:
                    continue
                    
                submissions.append({
                    'id': entry['id'],
                    'form_id': entry['form_id'],
                    'date': entry_date,
                    'fields': entry,
                    'ip': entry.get('ip', ''),
                    'source_url': entry.get('source_url', ''),
                    'user_agent': entry.get('user_agent', ''),
                    'source': 'gravity_forms'
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Gravity Forms entries: {e}")
            
        return submissions
    
    def get_comments_as_leads(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Get WordPress comments that might contain lead information.
        
        Args:
            since: Get comments since this datetime (optional)
            
        Returns:
            List of comments formatted as leads
        """
        leads = []
        
        try:
            endpoint = f"{self.site_url}/wp-json/wp/v2/comments"
            params = {"per_page": 100, "page": 1}
            
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            comments = response.json()
            
            for comment in comments:
                comment_date = datetime.fromisoformat(comment['date'])
                if since and comment_date < since:
                    continue
                    
                leads.append({
                    'id': f"comment_{comment['id']}",
                    'date': comment_date,
                    'name': comment.get('author_name', ''),
                    'email': comment.get('author_email', ''),
                    'website': comment.get('author_url', ''),
                    'content': comment.get('content', {}).get('rendered', ''),
                    'post_id': comment.get('post', ''),
                    'source': 'wordpress_comment'
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching comments: {e}")
            
        return leads
    
    def get_all_leads(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Get all leads from various sources.
        
        Args:
            since: Get leads since this datetime (optional)
            
        Returns:
            Combined list of all leads
        """
        all_leads = []
        
        # Try different form plugins
        logger.info("Fetching Contact Form 7 submissions...")
        all_leads.extend(self.get_contact_form_7_submissions(since=since))
        
        logger.info("Fetching WPForms submissions...")
        all_leads.extend(self.get_wpforms_submissions(since=since))
        
        logger.info("Fetching Gravity Forms entries...")
        all_leads.extend(self.get_gravity_forms_entries(since=since))
        
        logger.info("Fetching comments as potential leads...")
        all_leads.extend(self.get_comments_as_leads(since=since))
        
        logger.info(f"Total leads fetched: {len(all_leads)}")
        return all_leads
    
    def _get_cf7_from_database(self) -> List[Dict]:
        """
        Alternative method to get CF7 submissions if Flamingo is not available.
        This would require direct database access or custom endpoint.
        """
        logger.warning("Direct database access for CF7 not implemented. "
                      "Consider installing Flamingo plugin for CF7 submission storage.")
        return []