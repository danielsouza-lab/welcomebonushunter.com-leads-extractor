"""Lead data models for database storage."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, EmailStr, Field

Base = declarative_base()


class Lead(Base):
    """SQLAlchemy model for storing leads in database."""
    
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=False)  # ID from WordPress
    source = Column(String(50), nullable=False)  # e.g., 'contact_form_7', 'wpforms'
    form_name = Column(String(255))
    
    # Contact information
    name = Column(String(255))
    email = Column(String(255), index=True)
    phone = Column(String(50))
    company = Column(String(255))
    website = Column(String(255))
    
    # Lead details
    message = Column(Text)
    subject = Column(String(255))
    fields_data = Column(JSON)  # Store all form fields as JSON
    
    # Metadata
    ip_address = Column(String(45))
    user_agent = Column(Text)
    referrer_url = Column(String(500))
    page_url = Column(String(500))
    
    # Status tracking
    is_processed = Column(Boolean, default=False)
    is_qualified = Column(Boolean, default=False)
    notes = Column(Text)
    
    # Timestamps
    submitted_at = Column(DateTime, nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add indexes for common queries
    __table_args__ = (
        Index('idx_submitted_at', 'submitted_at'),
        Index('idx_source_processed', 'source', 'is_processed'),
        Index('idx_email_source', 'email', 'source'),
    )
    
    def __repr__(self):
        return f"<Lead(id={self.id}, email={self.email}, source={self.source})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary."""
        return {
            'id': self.id,
            'external_id': self.external_id,
            'source': self.source,
            'form_name': self.form_name,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'website': self.website,
            'message': self.message,
            'subject': self.subject,
            'fields_data': self.fields_data,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'referrer_url': self.referrer_url,
            'page_url': self.page_url,
            'is_processed': self.is_processed,
            'is_qualified': self.is_qualified,
            'notes': self.notes,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LeadSchema(BaseModel):
    """Pydantic schema for lead validation."""
    
    external_id: str
    source: str
    form_name: Optional[str] = None
    
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    
    message: Optional[str] = None
    subject: Optional[str] = None
    fields_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer_url: Optional[str] = None
    page_url: Optional[str] = None
    
    is_processed: bool = False
    is_qualified: bool = False
    notes: Optional[str] = None
    
    submitted_at: datetime
    extracted_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        
    @classmethod
    def from_wordpress_data(cls, data: Dict[str, Any]) -> 'LeadSchema':
        """
        Create LeadSchema from WordPress API response data.
        
        Args:
            data: Raw data from WordPress API
            
        Returns:
            LeadSchema instance
        """
        # Extract common fields
        external_id = str(data.get('id', ''))
        source = data.get('source', 'unknown')
        
        # Try to extract name and email from various field formats
        name = data.get('name', '')
        email = data.get('email', '')
        
        # Check fields_data for common field names
        fields = data.get('fields', {})
        if isinstance(fields, dict):
            name = name or fields.get('name', fields.get('your-name', fields.get('full_name', '')))
            email = email or fields.get('email', fields.get('your-email', fields.get('email_address', '')))
            phone = fields.get('phone', fields.get('your-phone', fields.get('phone_number', '')))
            company = fields.get('company', fields.get('company_name', ''))
            message = fields.get('message', fields.get('your-message', fields.get('comments', '')))
            subject = fields.get('subject', fields.get('your-subject', ''))
        else:
            phone = None
            company = None
            message = data.get('content', '')
            subject = data.get('subject', '')
        
        return cls(
            external_id=external_id,
            source=source,
            form_name=data.get('form_name', data.get('channel', '')),
            name=name,
            email=email,
            phone=phone,
            company=company,
            website=data.get('website', ''),
            message=message,
            subject=subject,
            fields_data=fields if isinstance(fields, dict) else {},
            ip_address=data.get('ip', data.get('ip_address', '')),
            user_agent=data.get('user_agent', ''),
            referrer_url=data.get('referrer_url', ''),
            page_url=data.get('source_url', data.get('page_url', '')),
            submitted_at=data.get('date', datetime.utcnow()),
            extracted_at=datetime.utcnow()
        )