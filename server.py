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
from datetime import datetime, timedelta
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

# CSRF protection
csrf = CSRFProtect(app)

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/escorts')
def escorts():
    return render_template('coming_soon.html')

@app.route('/adverts.json')
def get_adverts():
    try:
        with open('adverts.json', 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify([])

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

@app.route('/meet', methods=['POST'])
@csrf.exempt
def submit_meet_request():
    data = request.get_json()
    request_id = datetime.now().strftime('%Y%m%d%H%M%S')

    meet_request = {
        "id": request_id,
        "escortId": data.get('escortId'),
        "clientName": data.get('clientName'),
        "clientLocation": data.get('clientLocation'),
        "clientContact": data.get('clientContact'),
        "meetingDetails": data.get('meetingDetails'),
        "ageVerification": data.get('ageVerification'),
        "timestamp": datetime.utcnow().isoformat(),
        "status": "pending",
        "emergencyContact": "",
        "meetingDuration": 60,
        "safeWord": "pineapple",
        "scheduledTime": "",
        "safetyCheckIns": [],
        "lastCheckIn": None,
        "adminApproval": False,
        "safetyWarnings": []
    }

    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except FileNotFoundError:
        meet_requests = []

    meet_requests.append(meet_request)

    with open('meet_requests.json', 'w') as f:
        json.dump(meet_requests, f, indent=2)

    # Initialize chat messages for this request
    try:
        with open('chat_messages.json', 'r') as f:
            chat_messages = json.load(f)
    except FileNotFoundError:
        chat_messages = {}

    if request_id not in chat_messages:
        chat_messages[request_id] = []

    with open('chat_messages.json', 'w') as f:
        json.dump(chat_messages, f, indent=2)

    return jsonify({'success': True, 'request_id': request_id})

@app.route('/chat/<request_id>', methods=['GET'])
def get_chat_messages(request_id):
    try:
        with open('chat_messages.json', 'r') as f:
            chat_messages = json.load(f)
    except FileNotFoundError:
        chat_messages = {}

    messages = chat_messages.get(request_id, [])
    return jsonify({'messages': messages})

@app.route('/chat/<request_id>', methods=['POST'])
@csrf.exempt
def send_chat_message(request_id):
    if 'image' in request.files:
        image = request.files['image']
        if image:
            filename = secure_filename(str(uuid.uuid4()) + '_' + image.filename)
            image.save(os.path.join('uploads', filename))
            image_url = '/uploads/' + filename
        else:
            image_url = None
    else:
        image_url = None

    sender = request.form.get('sender')
    message = request.form.get('message', '')

    message_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

    chat_message = {
        "id": message_id,
        "sender": sender,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "image_url": image_url
    }

    try:
        with open('chat_messages.json', 'r') as f:
            chat_messages = json.load(f)
    except FileNotFoundError:
        chat_messages = {}

    if request_id not in chat_messages:
        chat_messages[request_id] = []

    chat_messages[request_id].append(chat_message)

    with open('chat_messages.json', 'w') as f:
        json.dump(chat_messages, f, indent=2)

    return jsonify({'success': True})

@app.route('/chat/<request_id>/end', methods=['POST'])
@csrf.exempt
def end_chat_session(request_id):
    message_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

    chat_message = {
        "id": message_id,
        "sender": "system",
        "message": "Chat session ended by administrator",
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        with open('chat_messages.json', 'r') as f:
            chat_messages = json.load(f)
    except FileNotFoundError:
        chat_messages = {}

    if request_id not in chat_messages:
        chat_messages[request_id] = []

    chat_messages[request_id].append(chat_message)

    with open('chat_messages.json', 'w') as f:
        json.dump(chat_messages, f, indent=2)

    return jsonify({'success': True})

@app.route('/videos.json')
@csrf.exempt
def get_videos():
    return send_from_directory('.', 'videos.json')

@app.route('/player.html')
def player_page():
    return send_from_directory('.', 'player.html')

@app.route('/game.html')
def game_page():
    return send_from_directory('.', 'game.html')

@app.route('/search.html')
def search_page():
    return send_from_directory('.', 'search.html')

@app.route('/chat.html')
def chat_page():
    return send_from_directory('.', 'chat.html')

@app.route('/group_chat.html')
def group_chat_page():
    return send_from_directory('.', 'group_chat.html')

@app.route('/analytics.html')
def analytics_page():
    return send_from_directory('.', 'analytics.html')

@app.route('/escorts.html')
def escorts_page():
    return send_from_directory('.', 'escorts.html')

@app.route('/apply-model', methods=['POST'])
@csrf.exempt
def apply_model():
    form_data = request.form
    photos = request.files.getlist('photos')

    photo_urls = []
    for photo in photos:
        if photo:
            filename = secure_filename(str(uuid.uuid4()) + '_' + photo.filename)
            photo.save(os.path.join('uploads', filename))
            photo_urls.append('/uploads/' + filename)

    application = ModelApplication(
        name=form_data['name'],
        location=form_data.get('location', ''),
        age=int(form_data['age']),
        height=form_data.get('height'),
        body_type=form_data.get('body_type'),
        town=form_data.get('town'),
        city=form_data.get('city'),
        country=form_data.get('country'),
        sexual_preference=form_data.get('sexual_preference'),
        occupation=form_data.get('occupation'),
        phone=form_data.get('phone'),
        email=form_data['email'],
        allergy=form_data.get('allergy'),
        skin_color=form_data.get('skin_color'),
        photos=json.dumps(photo_urls)
    )
    db.session.add(application)
    db.session.commit()

    return jsonify({'success': True, 'id': application.id})

@app.route('/group_chat/messages')
def get_group_chat_messages():
    try:
        with open('group_chat_messages.json', 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except FileNotFoundError:
        messages = []

    # Count unique users in recent messages (last 24 hours)
    recent_messages = [msg for msg in messages if datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00')) > datetime.utcnow() - timedelta(hours=24)]
    unique_users = len(set(msg['sender'] for msg in recent_messages))

    return jsonify({
        'success': True,
        'messages': messages,
        'online_count': max(unique_users, 1)  # At least 1 for current user
    })

@app.route('/group_chat/send', methods=['POST'])
@csrf.exempt
def send_group_chat_message():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'})

    try:
        with open('group_chat_messages.json', 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except FileNotFoundError:
        messages = []

    # Get next ID
    next_id = max([msg['id'] for msg in messages], default=0) + 1

    message = {
        'id': next_id,
        'sender': data.get('sender', 'Anonymous'),
        'user_id': data.get('user_id'),
        'message': data.get('message', ''),
        'timestamp': datetime.utcnow().isoformat(),
        'censored': data.get('was_censored', False)
    }

    messages.append(message)

    with open('group_chat_messages.json', 'w', encoding='utf-8') as f:
        json.dump(messages, f, indent=2)

    return jsonify({'success': True})
    form_data = request.form
    photos = request.files.getlist('photos')

    photo_urls = []
    for photo in photos:
        if photo:
            filename = secure_filename(str(uuid.uuid4()) + '_' + photo.filename)
            photo.save(os.path.join('uploads', filename))
            photo_urls.append('/uploads/' + filename)

    application = ModelApplication(
        name=form_data['name'],
        location=form_data.get('location', ''),
        age=int(form_data['age']),
        height=form_data.get('height'),
        body_type=form_data.get('body_type'),
        town=form_data.get('town'),
        city=form_data.get('city'),
        country=form_data.get('country'),
        sexual_preference=form_data.get('sexual_preference'),
        occupation=form_data.get('occupation'),
        phone=form_data.get('phone'),
        email=form_data['email'],
        allergy=form_data.get('allergy'),
        skin_color=form_data.get('skin_color'),
        photos=json.dumps(photo_urls)
    )
    db.session.add(application)
    db.session.commit()

    return jsonify({'success': True, 'id': application.id})

if __name__ == '__main__':
    app.run(debug=True)
