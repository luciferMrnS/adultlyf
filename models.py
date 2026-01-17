from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
import random

db = SQLAlchemy()

class Escort(db.Model):
    __tablename__ = 'escorts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    sexual_preference = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    photos = db.Column(db.Text)  # JSON string of photo URLs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'age': self.age,
            'location': self.location,
            'sexual_preference': self.sexual_preference,
            'description': self.description,
            'photos': json.loads(self.photos) if self.photos else []
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id'),
            name=data['name'],
            age=data['age'],
            location=data['location'],
            sexual_preference=data['sexual_preference'],
            description=data.get('description', ''),
            photos=json.dumps(data.get('photos', []))
        )

class ModelApplication(db.Model):
    __tablename__ = 'model_applications'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    height = db.Column(db.String(50))
    body_type = db.Column(db.String(50))
    town = db.Column(db.String(100))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    sexual_preference = db.Column(db.String(50))
    occupation = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200), nullable=False)
    allergy = db.Column(db.Text)
    skin_color = db.Column(db.String(50))
    photos = db.Column(db.Text)  # JSON string of photo URLs
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reviewed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'age': self.age,
            'height': self.height,
            'body_type': self.body_type,
            'town': self.town,
            'city': self.city,
            'country': self.country,
            'sexual_preference': self.sexual_preference,
            'occupation': self.occupation,
            'phone': self.phone,
            'email': self.email,
            'allergy': self.allergy,
            'skin_color': self.skin_color,
            'photos': json.loads(self.photos) if self.photos else [],
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'status': self.status,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }

    @classmethod
    def from_dict(cls, data):
        submitted_at = None
        if data.get('submitted_at'):
            try:
                submitted_at = datetime.fromisoformat(data['submitted_at'].replace('Z', '+00:00'))
            except:
                submitted_at = datetime.utcnow()

        reviewed_at = None
        if data.get('reviewed_at'):
            try:
                reviewed_at = datetime.fromisoformat(data['reviewed_at'].replace('Z', '+00:00'))
            except:
                reviewed_at = None

        return cls(
            id=data.get('id'),
            name=data['name'],
            location=data['location'],
            age=data['age'],
            height=data.get('height'),
            body_type=data.get('body_type'),
            town=data.get('town'),
            city=data.get('city'),
            country=data.get('country'),
            sexual_preference=data.get('sexual_preference'),
            occupation=data.get('occupation'),
            phone=data.get('phone'),
            email=data['email'],
            allergy=data.get('allergy'),
            skin_color=data.get('skin_color'),
            photos=json.dumps(data.get('photos', [])),
            submitted_at=submitted_at,
            status=data.get('status', 'pending'),
            reviewed_at=reviewed_at
        )

class SEOMetadata(db.Model):
    """SEO metadata for dynamic page optimization"""
    __tablename__ = 'seo_metadata'

    id = db.Column(db.Integer, primary_key=True)
    page_url = db.Column(db.String(500), unique=True, nullable=False)
    title = db.Column(db.String(200))
    description = db.Column(db.String(300))
    keywords = db.Column(db.Text)  # JSON array of keywords
    h1_tag = db.Column(db.String(200))
    canonical_url = db.Column(db.String(500))
    robots_meta = db.Column(db.String(100), default='index,follow')
    og_title = db.Column(db.String(200))
    og_description = db.Column(db.String(300))
    og_image = db.Column(db.String(500))
    twitter_card = db.Column(db.String(50), default='summary_large_image')
    structured_data = db.Column(db.Text)  # JSON-LD structured data
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    performance_score = db.Column(db.Float, default=0.0)

    def to_dict(self):
        return {
            'id': self.id,
            'page_url': self.page_url,
            'title': self.title,
            'description': self.description,
            'keywords': json.loads(self.keywords) if self.keywords else [],
            'h1_tag': self.h1_tag,
            'canonical_url': self.canonical_url,
            'robots_meta': self.robots_meta,
            'og_title': self.og_title,
            'og_description': self.og_description,
            'og_image': self.og_image,
            'twitter_card': self.twitter_card,
            'structured_data': json.loads(self.structured_data) if self.structured_data else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'performance_score': self.performance_score
        }

class SEOKeyword(db.Model):
    """Keyword tracking and optimization data"""
    __tablename__ = 'seo_keywords'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), unique=True, nullable=False)
    search_volume = db.Column(db.Integer, default=0)
    competition_level = db.Column(db.String(20), default='medium')  # low, medium, high
    current_ranking = db.Column(db.Integer)
    target_ranking = db.Column(db.Integer, default=10)
    monthly_searches = db.Column(db.Integer, default=0)
    cpc = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class SEOPerformance(db.Model):
    """SEO performance tracking"""
    __tablename__ = 'seo_performance'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    organic_traffic = db.Column(db.Integer, default=0)
    total_traffic = db.Column(db.Integer, default=0)
    bounce_rate = db.Column(db.Float, default=0.0)
    avg_session_duration = db.Column(db.Float, default=0.0)
    pages_per_session = db.Column(db.Float, default=0.0)
    new_users_percentage = db.Column(db.Float, default=0.0)
    top_landing_pages = db.Column(db.Text)  # JSON array
    top_keywords = db.Column(db.Text)  # JSON array
    backlinks_count = db.Column(db.Integer, default=0)
    domain_authority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SEOContent(db.Model):
    """Content optimization data"""
    __tablename__ = 'seo_content'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50))  # article, video, page, etc.
    content_id = db.Column(db.Integer)  # Reference to actual content
    title = db.Column(db.String(200))
    content_text = db.Column(db.Text)
    word_count = db.Column(db.Integer, default=0)
    readability_score = db.Column(db.Float, default=0.0)
    keyword_density = db.Column(db.Text)  # JSON object with keyword densities
    internal_links = db.Column(db.Text)  # JSON array of internal links
    external_links = db.Column(db.Text)  # JSON array of external links
    images_count = db.Column(db.Integer, default=0)
    videos_count = db.Column(db.Integer, default=0)
    last_optimized = db.Column(db.DateTime, default=datetime.utcnow)
    seo_score = db.Column(db.Float, default=0.0)

class SEOLink(db.Model):
    """Internal and external link tracking"""
    __tablename__ = 'seo_links'

    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(500), nullable=False)
    target_url = db.Column(db.String(500), nullable=False)
    link_type = db.Column(db.String(20), default='internal')  # internal, external
    anchor_text = db.Column(db.String(200))
    link_status = db.Column(db.String(20), default='active')  # active, broken, redirected
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    follow_attribute = db.Column(db.Boolean, default=True)

class SEOAutomation(db.Model):
    """SEO automation settings and schedules"""
    __tablename__ = 'seo_automation'

    id = db.Column(db.Integer, primary_key=True)
    automation_type = db.Column(db.String(50), nullable=False)  # meta_update, sitemap, keyword_refresh, etc.
    is_enabled = db.Column(db.Boolean, default=True)
    schedule_interval = db.Column(db.String(20), default='daily')  # hourly, daily, weekly, monthly
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    settings = db.Column(db.Text)  # JSON object with automation settings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_next_run(self):
        """Calculate when the next automation should run"""
        now = datetime.utcnow()
        if self.schedule_interval == 'hourly':
            self.next_run = now + timedelta(hours=1)
        elif self.schedule_interval == 'daily':
            self.next_run = now + timedelta(days=1)
        elif self.schedule_interval == 'weekly':
            self.next_run = now + timedelta(weeks=1)
        elif self.schedule_interval == 'monthly':
            # Approximate month as 30 days
            self.next_run = now + timedelta(days=30)
        else:
            self.next_run = now + timedelta(days=1)  # Default to daily
