from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

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
