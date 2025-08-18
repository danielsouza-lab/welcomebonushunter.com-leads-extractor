"""Database connection and session management."""

import logging
from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from src.wordpress_leads_extractor.models.lead import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL
            echo: Whether to echo SQL statements
        """
        self.database_url = database_url
        self.echo = echo
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        
    @property
    def engine(self) -> Engine:
        """Get or create database engine."""
        if self._engine is None:
            # Create engine with connection pooling
            self._engine = create_engine(
                self.database_url,
                echo=self.echo,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
            
            # Add event listener for SQLite to enable foreign keys
            if 'sqlite' in self.database_url:
                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_conn, connection_record):
                    cursor = dbapi_conn.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
                    
        return self._engine
    
    @property
    def session_factory(self) -> sessionmaker:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                expire_on_commit=False
            )
        return self._session_factory
    
    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables."""
        try:
            Base.metadata.drop_all(self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Error dropping database tables: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Yields:
            Database session
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def close(self):
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")


class LeadRepository:
    """Repository for lead database operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize lead repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    def save_lead(self, lead_data: dict) -> Optional[int]:
        """
        Save a lead to the database.
        
        Args:
            lead_data: Lead data dictionary
            
        Returns:
            Lead ID if saved successfully, None otherwise
        """
        from src.wordpress_leads_extractor.models.lead import Lead, LeadSchema
        
        try:
            # Validate data with Pydantic
            lead_schema = LeadSchema.from_wordpress_data(lead_data)
            
            with self.db.get_session() as session:
                # Check if lead already exists
                existing = session.query(Lead).filter_by(
                    external_id=lead_schema.external_id,
                    source=lead_schema.source
                ).first()
                
                if existing:
                    # Update existing lead
                    for key, value in lead_schema.dict(exclude={'id'}).items():
                        setattr(existing, key, value)
                    lead_id = existing.id
                    logger.info(f"Updated existing lead: {lead_id}")
                else:
                    # Create new lead
                    lead = Lead(**lead_schema.dict())
                    session.add(lead)
                    session.flush()
                    lead_id = lead.id
                    logger.info(f"Created new lead: {lead_id}")
                    
                return lead_id
                
        except Exception as e:
            logger.error(f"Error saving lead: {e}")
            return None
    
    def get_lead_by_id(self, lead_id: int) -> Optional[dict]:
        """
        Get a lead by ID.
        
        Args:
            lead_id: Lead ID
            
        Returns:
            Lead data dictionary or None
        """
        from src.wordpress_leads_extractor.models.lead import Lead
        
        try:
            with self.db.get_session() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if lead:
                    return lead.to_dict()
                return None
        except Exception as e:
            logger.error(f"Error getting lead: {e}")
            return None
    
    def get_unprocessed_leads(self, limit: int = 100) -> list:
        """
        Get unprocessed leads.
        
        Args:
            limit: Maximum number of leads to return
            
        Returns:
            List of lead dictionaries
        """
        from src.wordpress_leads_extractor.models.lead import Lead
        
        try:
            with self.db.get_session() as session:
                leads = session.query(Lead).filter_by(
                    is_processed=False
                ).limit(limit).all()
                return [lead.to_dict() for lead in leads]
        except Exception as e:
            logger.error(f"Error getting unprocessed leads: {e}")
            return []
    
    def mark_lead_processed(self, lead_id: int, notes: str = None) -> bool:
        """
        Mark a lead as processed.
        
        Args:
            lead_id: Lead ID
            notes: Optional notes
            
        Returns:
            True if successful, False otherwise
        """
        from src.wordpress_leads_extractor.models.lead import Lead
        
        try:
            with self.db.get_session() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if lead:
                    lead.is_processed = True
                    if notes:
                        lead.notes = notes
                    return True
                return False
        except Exception as e:
            logger.error(f"Error marking lead as processed: {e}")
            return False
    
    def get_leads_count(self, source: str = None, processed: bool = None) -> int:
        """
        Get count of leads.
        
        Args:
            source: Filter by source (optional)
            processed: Filter by processed status (optional)
            
        Returns:
            Number of leads
        """
        from src.wordpress_leads_extractor.models.lead import Lead
        
        try:
            with self.db.get_session() as session:
                query = session.query(Lead)
                
                if source:
                    query = query.filter_by(source=source)
                if processed is not None:
                    query = query.filter_by(is_processed=processed)
                    
                return query.count()
        except Exception as e:
            logger.error(f"Error counting leads: {e}")
            return 0