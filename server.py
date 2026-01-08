from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect
from flask_wtf import FlaskForm, CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FileField, MultipleFileField
from wtforms.validators import DataRequired, Length, NumberRange
import subprocess
import sys
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system environment variables

# Import shuffle functionality
try:
    from scraper import start_shuffle_scheduler, shuffle_videos, start_autonomous_scraper
    SHUFFLE_AVAILABLE = True
    AUTONOMOUS_SCRAPER_AVAILABLE = True
except ImportError:
    SHUFFLE_AVAILABLE = False
    AUTONOMOUS_SCRAPER_AVAILABLE = False
    print("Warning: Scraper functionality not available (scraper.py not found)")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Enforce HTTPS in production
@app.before_request
def enforce_https():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# Hashed admin password - in production, use proper authentication
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'passhavok'))

# Form classes for CSRF protection
class AdminLoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])

class EscortForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=18, max=99)])
    location = StringField('Location', validators=[DataRequired(), Length(min=2, max=200)])
    sexual_preference = StringField('Sexual Preference', validators=[DataRequired(), Length(min=2, max=50)])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    photos = MultipleFileField('Photos')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/index.html')
def index_html():
    return send_from_directory('.', 'index.html')

@app.route('/player.html')
def player():
    return send_from_directory('.', 'player.html')

@app.route('/search.html')
def search():
    return send_from_directory('.', 'search.html')

@app.route('/videos.json')
def videos():
    return send_from_directory('.', 'videos.json')

@app.route('/adverts.json')
def adverts():
    return send_from_directory('.', 'adverts.json')

@app.route('/keywords.json')
def keywords():
    return send_from_directory('.', 'keywords.json')

@app.route('/apply-model', methods=['POST'])
@limiter.limit("5 per hour", methods=["POST"])  # Limit model applications
def apply_model():
    data = request.get_json()

    # Validate required fields
    required_fields = ['name', 'location', 'age', 'height', 'body_type', 'town', 'city', 'country', 'sexual_preference', 'phone', 'email', 'skin_color']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate age
    age = data.get('age')
    if not isinstance(age, int) or age < 18 or age > 99:
        return jsonify({'error': 'Age must be between 18 and 99'}), 400

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, data.get('email', '')):
        return jsonify({'error': 'Invalid email format'}), 400

    # Load existing model applications
    try:
        with open('model_applications.json', 'r') as f:
            model_applications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        model_applications = []

    # Generate new ID
    new_id = max([app.get('id', 0) for app in model_applications], default=0) + 1

    # Create application
    application = {
        'id': new_id,
        'name': data['name'],
        'location': data['location'],
        'age': age,
        'height': data['height'],
        'body_type': data['body_type'],
        'town': data['town'],
        'city': data['city'],
        'country': data['country'],
        'sexual_preference': data['sexual_preference'],
        'occupation': data.get('occupation', ''),
        'phone': data['phone'],
        'email': data['email'],
        'allergy': data.get('allergy', ''),
        'skin_color': data['skin_color'],
        'submitted_at': data.get('submitted_at', datetime.now().isoformat()),
        'status': 'pending'  # pending, approved, rejected
    }

    model_applications.append(application)

    # Save to file
    with open('model_applications.json', 'w') as f:
        json.dump(model_applications, f, indent=4)

    return jsonify({
        'success': True,
        'message': 'Model application submitted successfully',
        'application_id': new_id
    })

@app.route('/update-model-status/<int:application_id>', methods=['POST'])
def update_model_status(application_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['pending', 'approved', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    # Load existing applications
    try:
        with open('model_applications.json', 'r') as f:
            applications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Applications file not found'}), 404

    # Find and update the application
    for i, app in enumerate(applications):
        if app['id'] == application_id:
            applications[i]['status'] = new_status
            applications[i]['reviewed_at'] = datetime.now().isoformat()

            # Save back to file
            with open('model_applications.json', 'w') as f:
                json.dump(applications, f, indent=4)

            return jsonify({
                'success': True,
                'message': f'Application status updated to {new_status}',
                'application': applications[i]
            })

    return jsonify({'error': 'Application not found'}), 404

@app.route('/model_applications.json')
def model_applications_json():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return send_from_directory('.', 'model_applications.json')

@app.route('/meet_requests.json')
def meet_requests_json():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return send_from_directory('.', 'meet_requests.json')

@app.route('/scrape', methods=['POST'])
@limiter.limit("10 per hour", methods=["POST"])
def scrape():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400

    # Validate keyword - only allow alphanumeric characters, spaces, and basic punctuation
    import re
    if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', keyword):
        return jsonify({'error': 'Keyword contains invalid characters'}), 400

    # Limit keyword length
    if len(keyword) > 50:
        return jsonify({'error': 'Keyword too long'}), 400

    try:
        # Run the scraper with the keyword - use shell=False to prevent injection
        result = subprocess.run([sys.executable, 'scraper.py', keyword],
                              capture_output=True, text=True, cwd=os.getcwd(), shell=False)

        if result.returncode == 0:
            # Try to read the updated videos.json to return the new videos
            try:
                import json
                with open('videos.json', 'r', encoding='utf-8') as f:
                    all_videos = json.load(f)

                # Find videos that contain the keyword in title
                matching_videos = [v for v in all_videos
                                 if keyword.lower() in v.get('title', '').lower()]

                return jsonify({
                    'success': True,
                    'message': f'Scraped {len(matching_videos)} videos for "{keyword}"',
                    'videos': matching_videos[:20]  # Return up to 20 videos
                })
            except Exception as e:
                return jsonify({
                    'success': True,
                    'message': f'Scraping completed for "{keyword}", but could not read results: {str(e)}'
                })
        else:
            return jsonify({
                'error': 'Scraping failed',
                'details': result.stderr
            }), 500

    except Exception as e:
        return jsonify({
            'error': 'Server error during scraping',
            'details': str(e)
        }), 500

@app.route('/escorts.html')
def escorts():
    return send_from_directory('.', 'escorts.html')

@app.route('/escorts.json')
def escorts_json():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return send_from_directory('.', 'escorts.json')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
    return send_from_directory(upload_dir, filename)

@app.route('/admin/escorts/<int:escort_id>', methods=['PUT', 'DELETE'])
def manage_escort(escort_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    # Load existing escorts
    try:
        with open('escorts.json', 'r') as f:
            escorts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        escorts = []

    if request.method == 'DELETE':
        # Delete escort
        escorts = [e for e in escorts if e['id'] != escort_id]

        # Save back to file
        with open('escorts.json', 'w') as f:
            json.dump(escorts, f, indent=4)

        return jsonify({
            'success': True,
            'message': f'Escort ID {escort_id} deleted successfully'
        })

    elif request.method == 'PUT':
        # Update escort - handle both JSON and form data for file uploads
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file uploads
            data = request.form
            uploaded_files = request.files.getlist('photos')
            photo_paths = []

            if uploaded_files and any(f.filename for f in uploaded_files):
                # New photos uploaded, replace existing ones
                for file in uploaded_files:
                    if file and file.filename:
                        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                        # Use Railway volume path if available, otherwise local uploads
                        upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
                        os.makedirs(upload_dir, exist_ok=True)
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        photo_paths.append(f"/uploads/{filename}")
        else:
            # JSON data (for non-file updates)
            data = request.get_json()
            photo_paths = None

        for i, escort in enumerate(escorts):
            if escort['id'] == escort_id:
                # Update fields
                if 'name' in data:
                    escorts[i]['name'] = data['name']
                if 'age' in data:
                    escorts[i]['age'] = int(data['age'])
                if 'location' in data:
                    escorts[i]['location'] = data['location']
                if 'sexual_preference' in data:
                    escorts[i]['sexual_preference'] = data['sexual_preference']
                if 'description' in data:
                    escorts[i]['description'] = data['description']
                if photo_paths is not None:
                    escorts[i]['photos'] = photo_paths

                # Save back to file
                with open('escorts.json', 'w') as f:
                    json.dump(escorts, f, indent=4)

                return jsonify({
                    'success': True,
                    'message': f'Escort {escorts[i]["name"]} updated successfully',
                    'escort': escorts[i]
                })

        return jsonify({'error': 'Escort not found'}), 404

@app.route('/meet', methods=['POST'])
@limiter.limit("20 per hour", methods=["POST"])  # Limit meeting requests
def meet():
    data = request.get_json()

    required_fields = ['escortId', 'clientName', 'clientLocation', 'clientContact', 'ageVerification']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate age verification
    if data.get('ageVerification') != 'yes':
        return jsonify({'error': 'You must be 18 or older to submit a meeting request'}), 400

    # Input validation and sanitization
    client_name = data.get('clientName', '').strip()
    client_location = data.get('clientLocation', '').strip()
    client_contact = data.get('clientContact', '').strip()
    meeting_details = data.get('meetingDetails', '').strip()

    # Validate lengths
    if len(client_name) > 100 or len(client_name) < 2:
        return jsonify({'error': 'Client name must be between 2 and 100 characters'}), 400
    if len(client_location) > 200:
        return jsonify({'error': 'Location too long'}), 400
    if len(client_contact) > 200:
        return jsonify({'error': 'Contact information too long'}), 400
    if len(meeting_details) > 1000:
        return jsonify({'error': 'Meeting details too long'}), 400

    # Basic sanitization - remove potentially harmful characters
    import re
    if re.search(r'[<>]', client_name + client_location + client_contact):
        return jsonify({'error': 'Input contains invalid characters'}), 400

    # Update data with sanitized values
    data['clientName'] = client_name
    data['clientLocation'] = client_location
    data['clientContact'] = client_contact
    data['meetingDetails'] = meeting_details

    # Enhanced safety validation
    safety_fields = ['emergencyContact', 'meetingDuration', 'safeWord']
    safety_warnings = []

    for field in safety_fields:
        if not data.get(field):
            safety_warnings.append(f"Warning: {field.replace('_', ' ')} not provided")

    # Create meet request with safety features
    meet_request = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S'),
        'escortId': data['escortId'],
        'clientName': data['clientName'],
        'clientLocation': data['clientLocation'],
        'clientContact': data['clientContact'],
        'emergencyContact': data.get('emergencyContact', ''),
        'meetingDuration': data.get('meetingDuration', 60),  # minutes
        'safeWord': data.get('safeWord', 'pineapple'),  # default safe word
        'meetingDetails': data.get('meetingDetails', ''),
        'timestamp': datetime.now().isoformat(),
        'scheduledTime': data.get('scheduledTime', ''),
        'status': 'pending',
        'safetyCheckIns': [],
        'lastCheckIn': None,
        'adminApproval': False,
        'safetyWarnings': safety_warnings
    }

    # Load existing meet requests
    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        meet_requests = []

    # Add new request
    meet_requests.append(meet_request)

    # Save back to file
    with open('meet_requests.json', 'w') as f:
        json.dump(meet_requests, f, indent=4)

    response_message = 'Meeting request submitted successfully. Admin will review for safety before approval.'
    if safety_warnings:
        response_message += f" Safety concerns: {', '.join(safety_warnings)}"

    return jsonify({
        'success': True,
        'message': response_message,
        'request_id': meet_request['id'],
        'safety_warnings': safety_warnings,
        'chat_enabled': True
    })

@app.route('/meet/<request_id>/checkin', methods=['POST'])
def safety_checkin(request_id):
    """Safety check-in endpoint for ongoing meetings"""
    data = request.get_json()
    checkin_type = data.get('type', 'status')  # 'status', 'emergency', 'end'

    # Load meet requests
    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Meeting request not found'}), 404

    # Find the request
    request_found = None
    for req in meet_requests:
        if req['id'] == request_id:
            request_found = req
            break

    if not request_found:
        return jsonify({'error': 'Meeting request not found'}), 404

    # Record check-in
    checkin_record = {
        'timestamp': datetime.now().isoformat(),
        'type': checkin_type,
        'message': data.get('message', ''),
        'location': data.get('location', '')
    }

    if 'safetyCheckIns' not in request_found:
        request_found['safetyCheckIns'] = []

    request_found['safetyCheckIns'].append(checkin_record)
    request_found['lastCheckIn'] = checkin_record['timestamp']

    # Handle emergency
    if checkin_type == 'emergency':
        request_found['status'] = 'emergency'
        # In production, this should trigger notifications to admin and emergency contacts

    # Save updated requests
    with open('meet_requests.json', 'w') as f:
        json.dump(meet_requests, f, indent=4)

    return jsonify({
        'success': True,
        'message': f'Check-in recorded: {checkin_type}',
        'checkin': checkin_record
    })

@app.route('/meet/<request_id>/end', methods=['POST'])
def end_meeting(request_id):
    """End a meeting safely"""
    # Load meet requests
    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Meeting request not found'}), 404

    # Find and update the request
    for req in meet_requests:
        if req['id'] == request_id:
            req['status'] = 'completed'
            req['endTime'] = datetime.now().isoformat()

            # Save updated requests
            with open('meet_requests.json', 'w') as f:
                json.dump(meet_requests, f, indent=4)

            return jsonify({
                'success': True,
                'message': 'Meeting ended safely. Thank you for the safe check-in.',
                'end_time': req['endTime']
            })

    return jsonify({'error': 'Meeting request not found'}), 404

# Chat system endpoints
@app.route('/chat/<request_id>', methods=['GET'])
def get_chat_messages(request_id):
    """Get all chat messages for a request"""
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_messages = {}

    messages = all_messages.get(request_id, [])
    return jsonify({'messages': messages})

@app.route('/chat/<request_id>', methods=['POST'])
@limiter.limit("100 per hour", methods=["POST"])  # Chat message limits
def send_chat_message(request_id):
    """Send a chat message"""
    data = request.get_json()
    sender = data.get('sender', 'unknown')  # 'client' or 'admin'
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # Load existing messages
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_messages = {}

    if request_id not in all_messages:
        all_messages[request_id] = []

    # Add new message
    chat_message = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
        'sender': sender,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }

    all_messages[request_id].append(chat_message)

    # Save messages
    with open('chat_messages.json', 'w') as f:
        json.dump(all_messages, f, indent=4)

    return jsonify({
        'success': True,
        'message': chat_message
    })

@app.route('/chat/<request_id>/end', methods=['POST'])
def end_chat_session(request_id):
    """End a chat session - removes it from active status"""
    # Load existing messages
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_messages = {}

    if request_id in all_messages:
        # Add an end message to the chat
        end_message = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
            'sender': 'system',
            'message': 'Chat session ended by administrator',
            'timestamp': datetime.now().isoformat()
        }
        all_messages[request_id].append(end_message)

        # Save the final messages
        with open('chat_messages.json', 'w') as f:
            json.dump(all_messages, f, indent=4)

        return jsonify({
            'success': True,
            'message': 'Chat session ended successfully'
        })
    else:
        return jsonify({
            'error': 'Chat session not found'
        }), 404

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])  # Strict limit for admin login
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        password = form.password.data
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect('/admin/escorts')
        else:
            return render_template('admin_login.html', form=form, error='Invalid password')
    return render_template('admin_login.html', form=form)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

def require_admin_login():
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')

@app.route('/admin/escorts', methods=['GET', 'POST'])
@limiter.limit("30 per hour", methods=["POST"])  # Admin operations limits
def admin_escorts():
    login_check = require_admin_login()
    if login_check:
        return login_check

    if request.method == 'POST':
        # Create new escort profile
        data = request.form

        required_fields = ['name', 'age', 'location', 'sexual_preference']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        # Handle file uploads
        uploaded_files = request.files.getlist('photos')
        photo_paths = []

        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            return jsonify({'error': 'At least one photo is required'}), 400

        for file in uploaded_files:
            if file and file.filename:
                # Generate unique filename
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                # Use Railway volume path if available, otherwise local uploads
                upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                # Serve from the correct path
                photo_paths.append(f"/uploads/{filename}")

        # Load existing escorts
        try:
            with open('escorts.json', 'r') as f:
                escorts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            escorts = []

        # Generate new ID
        new_id = max([e.get('id', 0) for e in escorts], default=0) + 1

        # Create escort profile
        escort = {
            'id': new_id,
            'name': data['name'],
            'age': int(data['age']),
            'location': data['location'],
            'sexual_preference': data['sexual_preference'],
            'photos': photo_paths,
            'description': data.get('description', '')
        }

        escorts.append(escort)

        # Save back to file
        with open('escorts.json', 'w') as f:
            json.dump(escorts, f, indent=4)

        return jsonify({
            'success': True,
            'message': f'Escort profile for {escort["name"]} created successfully',
            'escort': escort
        })

    else:
        # Show admin panel
        try:
            with open('meet_requests.json', 'r') as f:
                meet_requests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            meet_requests = []

        # Get escort names for display
        try:
            with open('escorts.json', 'r') as f:
                escorts = json.load(f)
            escort_names = {e['id']: e['name'] for e in escorts}
        except:
            escort_names = {}

        # Add escort names to requests
        for req in meet_requests:
            req['escort_name'] = escort_names.get(int(req['escortId']), 'Unknown')

        # Prepare escorts data for JavaScript
        escorts_data = {e['id']: e for e in escorts}

        return render_template('admin_escorts.html',
                               escorts=escorts,
                               meet_requests=meet_requests,
                               escorts_data=escorts_data)

if __name__ == '__main__':
    # Start the video shuffle scheduler
    if SHUFFLE_AVAILABLE:
        start_shuffle_scheduler()
    else:
        print("Video shuffling not available - scraper.py not found")

    # Start the autonomous scraper
    if AUTONOMOUS_SCRAPER_AVAILABLE:
        start_autonomous_scraper()
    else:
        print("Autonomous scraper not available - scraper.py not found")

    # Production-ready configuration
    port = int(os.environ.get('PORT', 8000))

    # Only run development server if explicitly requested
    if os.environ.get('FLASK_ENV') == 'development':
        print("🚀 Starting Flask development server...")
        print(f"⚠️  WARNING: This is a development server. Do not use in production!")
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        print("✅ Production mode: Use Gunicorn or another WSGI server")
        print("   Example: gunicorn --bind 0.0.0.0:8000 --workers 4 server:app")
        print("   Railway will automatically use production server")
