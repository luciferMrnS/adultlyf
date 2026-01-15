from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect
from flask_wtf import FlaskForm, CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FileField, MultipleFileField
from wtforms.validators import DataRequired, Length, NumberRange
import subprocess
import sys
import os
import json
import re
import html
from datetime import datetime
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database models
from models import db, Escort, ModelApplication

# Import scraper functions for video shuffling
from scraper import start_shuffle_scheduler, start_autonomous_scraper

# Initialize Flask app
app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///adultlyf.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Migrate data on startup
with app.app_context():
    db.create_all()
    # Migrate escorts data
    if Escort.query.count() == 0:
        try:
            with open('escorts.json', 'r') as f:
                escorts_data = json.load(f)
                for escort_data in escorts_data:
                    escort = Escort.from_dict(escort_data)
                    db.session.add(escort)
                db.session.commit()
        except FileNotFoundError:
            pass
    # Migrate model applications data
    if ModelApplication.query.count() == 0:
        try:
            with open('model_applications.json', 'r') as f:
                apps_data = json.load(f)
                for app_data in apps_data:
                    application = ModelApplication.from_dict(app_data)
                    db.session.add(application)
                db.session.commit()
        except FileNotFoundError:
            pass

# Start background services
start_shuffle_scheduler()
start_autonomous_scraper()

# Routes

@app.route('/escorts.json')
def get_escorts():
    escorts = Escort.query.all()
    return jsonify([escort.to_dict() for escort in escorts])

@app.route('/model_applications.json')
def get_model_applications():
    applications = ModelApplication.query.all()
    return jsonify([app.to_dict() for app in applications])

# Admin routes
@app.route('/admin/escorts', methods=['POST'])
def create_escort():
    data = request.form
    photos = request.files.getlist('photos')

    photo_urls = []
    for photo in photos:
        if photo:
            filename = secure_filename(str(uuid.uuid4()) + '_' + photo.filename)
            photo.save(os.path.join('uploads', filename))
            photo_urls.append('/uploads/' + filename)

    escort = Escort(
        name=data['name'],
        age=int(data['age']),
        location=data['location'],
        sexual_preference=data['sexual_preference'],
        description=data.get('description', ''),
        photos=json.dumps(photo_urls)
    )
    db.session.add(escort)
    db.session.commit()

    return jsonify({'success': True, 'id': escort.id})

@app.route('/admin/escorts/<int:escort_id>', methods=['PUT'])
def update_escort(escort_id):
    escort = Escort.query.get_or_404(escort_id)
    data = request.form
    photos = request.files.getlist('photos')

    photo_urls = json.loads(escort.photos) if escort.photos else []

    # Handle photo deletions
    photos_to_delete = request.form.get('photosToDelete', '')
    if photos_to_delete:
        indices_to_delete = [int(i) for i in photos_to_delete.split(',')]
        # Remove from list
        photo_urls = [url for i, url in enumerate(photo_urls) if i not in indices_to_delete]

    # Add new photos
    for photo in photos:
        if photo and photo.filename:
            filename = secure_filename(str(uuid.uuid4()) + '_' + photo.filename)
            photo.save(os.path.join('uploads', filename))
            photo_urls.append('/uploads/' + filename)

    escort.name = data['name']
    escort.age = int(data['age'])
    escort.location = data['location']
    escort.sexual_preference = data['sexual_preference']
    escort.description = data.get('description', '')
    escort.photos = json.dumps(photo_urls)
    escort.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({'success': True})

@app.route('/admin/escorts/<int:escort_id>', methods=['DELETE'])
def delete_escort(escort_id):
    escort = Escort.query.get_or_404(escort_id)
    db.session.delete(escort)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/update-model-status/<int:app_id>', methods=['POST'])
def update_model_status(app_id):
    application = ModelApplication.query.get_or_404(app_id)
    data = request.json
    application.status = data['status']
    application.reviewed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/delete-model-application/<int:app_id>', methods=['DELETE'])
def delete_model_application(app_id):
    application = ModelApplication.query.get_or_404(app_id)
    db.session.delete(application)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/escorts')
def admin_escorts():
    escorts = Escort.query.all()
    escorts_data = [escort.to_dict() for escort in escorts]
    return render_template('admin_escorts.html', escorts=escorts_data, escorts_data=escorts_data)

if __name__ == '__main__':
    app.run(debug=True)
