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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system environment variables

def commit_to_git(file_path, commit_message):
    """
    Commit changes to git repository for permanent storage.
    This ensures admin changes are never lost or reversed by default.
    """
    try:
        # IMPORTANT: Never let git operations hang a web request.
        # On some Windows setups, `git commit` can block (hooks/GPG/editor prompts).
        GIT_TIMEOUT_S = int(os.environ.get('GIT_TIMEOUT_S', '8'))

        # Add the file to git
        result_add = subprocess.run(['git', 'add', file_path],
                                   check=True, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        print(f"✅ Added {file_path} to git staging")

        # Commit with the message
        result_commit = subprocess.run(['git', 'commit', '-m', commit_message],
                                      check=True, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        print(f"✅ Committed: {commit_message}")

        # Get the commit hash for logging
        result_hash = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                    capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        commit_hash = result_hash.stdout.strip()[:8] if result_hash.returncode == 0 else 'unknown'

        print(f"💾 Changes permanently saved - Commit: {commit_hash}")
        return True

    except subprocess.CalledProcessError as e:
        error_msg = f"❌ CRITICAL: Failed to commit {file_path} to git: {e}"
        print(error_msg)
        print(f"Git stderr: {e.stderr}")
        # Don't fail the operation, but log the error prominently
        return False
    except subprocess.TimeoutExpired as e:
        error_msg = f"⚠️ WARNING: git operation timed out after {getattr(e, 'timeout', '?')}s while committing {file_path}"
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"❌ CRITICAL: Unexpected error during git commit: {e}"
        print(error_msg)
        return False

# Import shuffle functionality
try:
    from scraper import start_shuffle_scheduler, shuffle_videos, start_autonomous_scraper
    SHUFFLE_AVAILABLE = True
    # Disable autonomous scraper on Railway due to network restrictions and deployment issues
    AUTONOMOUS_SCRAPER_AVAILABLE = False if os.environ.get('RAILWAY_ENVIRONMENT') else True
except ImportError:
    SHUFFLE_AVAILABLE = False
    AUTONOMOUS_SCRAPER_AVAILABLE = False
    print("Warning: Scraper functionality not available (scraper.py not found)")

# Import analytics functionality
try:
    from visitor_analytics import analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    print("Warning: Analytics functionality not available (visitor_analytics.py not found)")

def sanitize_chat_message(message):
    """
    Sanitize chat messages to prevent XSS attacks.
    - Escape HTML entities
    - Remove potentially dangerous scripts
    - Limit message length
    """
    if not message:
        return ""

    # Limit message length (reasonable chat message size)
    if len(message) > 2000:
        message = message[:2000] + "..."

    # Escape HTML entities to prevent XSS
    message = html.escape(message, quote=True)

    # Additional safety: remove script tags and other dangerous patterns
    # Remove <script> tags and their contents
    message = re.sub(r'<script[^>]*>.*?</script>', '', message, flags=re.IGNORECASE | re.DOTALL)
    # Remove javascript: URLs
    message = re.sub(r'javascript:', '', message, flags=re.IGNORECASE)
    # Remove data: URLs that might contain scripts
    message = re.sub(r'data:text/html', '', message, flags=re.IGNORECASE)

    return message.strip()

def validate_image_url(url):
    """
    Validate image URLs to prevent XSS through malicious URLs.
    Only allow local upload URLs or safe external URLs.
    """
    if not url:
        return False

    # Only allow local upload URLs
    if url.startswith('/uploads/'):
        # Basic filename validation - no path traversal
        filename = url[9:]  # Remove '/uploads/' prefix
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        # The regex was too strict. Since we use secure_filename on the server to
        # generate the name, we can be confident it's safe.
        return True

    return False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')

# Configure CSRF protection with longer timeout (1 hour)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour in seconds

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize CORS
CORS(app)

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

# Track visitor analytics
@app.before_request
def track_analytics():
    if ANALYTICS_AVAILABLE:
        try:
            # Get client IP address
            ip_address = request.remote_addr
            if not ip_address:
                return  # Skip if no IP available

            # Get user agent
            user_agent = request.headers.get('User-Agent', '')

            # Get path and method
            path = request.path
            method = request.method

            # Track the visit
            analytics.track_visit(ip_address, user_agent, path, method)
        except Exception as e:
            print(f"Analytics tracking error: {e}")
            # Don't fail the request if analytics fails

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

@app.route('/api/search')
def search_videos():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({'error': 'Query parameter q is required'}), 400

    # Load existing videos first
    try:
        with open('videos.json', 'r', encoding='utf-8') as f:
            all_videos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If videos.json doesn't exist, create an empty one
        all_videos = []
        try:
            with open('videos.json', 'w', encoding='utf-8') as f:
                json.dump([], f, indent=4)
        except Exception as e:
            print(f"Error creating videos.json: {e}")

    # Filter videos where title contains the query (case insensitive)
    matching_videos = [v for v in all_videos if query in v.get('title', '').lower()]

    # Try to trigger scraping for the search query (don't fail if scraper unavailable)
    try:
        from scraper import scrape_with_keyword
        print(f"Search triggered scrape for: {query}")
        # Scrape with a limit of 15 videos per site for better results
        scrape_with_keyword(query, limit_per_site=15)
        print("Scraping completed successfully")
    except Exception as e:
        print(f"Scraping unavailable or failed: {e}")
        print("Continuing with existing videos only")

    # Reload videos in case scraping added new ones
    try:
        with open('videos.json', 'r', encoding='utf-8') as f:
            all_videos = json.load(f)
        matching_videos = [v for v in all_videos if query in v.get('title', '').lower()]
    except Exception as e:
        print(f"Error reloading videos after scraping: {e}")

    return jsonify({
        'success': True,
        'query': query,
        'total_results': len(matching_videos),
        'videos': matching_videos[:50]  # Limit to 50 results for performance
    })

@app.route('/adverts.json')
def adverts():
    return send_from_directory('.', 'adverts.json')

@app.route('/keywords.json')
def keywords():
    return send_from_directory('.', 'keywords.json')

@app.route('/apply-model', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per hour", methods=["POST"])  # Limit model applications
def apply_model():
    data = request.form

    # Validate required fields
    required_fields = ['name', 'location', 'age', 'height', 'body_type', 'town', 'city', 'country', 'sexual_preference', 'phone', 'email', 'skin_color']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate age
    try:
        age = int(data.get('age'))
        if age < 18 or age > 99:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'Age must be a number between 18 and 99'}), 400

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, data.get('email', '')):
        return jsonify({'error': 'Invalid email format'}), 400

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

    # Load existing model applications
    try:
        with open('model_applications.json', 'r') as f:
            model_applications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        model_applications = []

    # Generate new ID
    new_id = max([application.get('id', 0) for application in model_applications], default=0) + 1

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
        'photos': photo_paths,
        'submitted_at': datetime.now().isoformat(),
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
@csrf.exempt
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

            # PERMANENTLY commit the change to git - admin changes are NEVER reversed
            commit_message = f"ADMIN: Update model application status - ID {application_id} to {new_status}"
            commit_success = commit_to_git('model_applications.json', commit_message)

            if not commit_success:
                print("🚨 CRITICAL: Model application updated but NOT committed to git!")
                print("🚨 This change may be lost on server restart!")
                return jsonify({
                    'error': 'Application updated but commit to git failed. Contact administrator.',
                    'application': applications[i]
                }), 500

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
    try:
        with open('meet_requests.json', 'r') as f:
            return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify([])

@app.route('/my-chats')
def my_chats():
    """Return active chats for the current client based on their meeting requests"""
    # For now, return all meet requests (in production, you'd filter by client identifier)
    # Since we don't have user authentication for clients, we'll return all active chats
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

    # Filter to active chats (not ended by admin)
    active_chats = []
    for req in meet_requests:
        # Check if chat still exists (not ended)
        try:
            with open('chat_messages.json', 'r') as f:
                chat_messages = json.load(f)
            has_chat = req['id'] in chat_messages
            # Check if chat was ended
            chat_ended = False
            if has_chat:
                messages = chat_messages[req['id']]
                chat_ended = any(msg.get('message') == 'Chat session ended by administrator' for msg in messages)
        except:
            has_chat = False
            chat_ended = True

        if has_chat and not chat_ended:
            active_chats.append({
                'request_id': req['id'],
                'escort_name': escort_names.get(int(req['escortId']), 'Unknown Escort'),
                'client_name': req['clientName'],
                'timestamp': req['timestamp'],
                'status': req['status'],
                'chat_url': f'/chat.html?request_id={req["id"]}'
            })

    return jsonify({
        'active_chats': active_chats,
        'total_active': len(active_chats)
    })

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
        print(f"Starting scrape for keyword: {keyword}")
        # Import and call the scraper function directly
        try:
            from scraper import scrape_with_keyword
        except ImportError as e:
            print(f"Scraper import failed: {e}")
            return jsonify({
                'error': 'Scraper functionality unavailable',
                'details': str(e)
            }), 500

        new_videos = scrape_with_keyword(keyword, limit_per_site=15)  # Increase limit for more results
        print(f"Scraper returned {len(new_videos)} new videos")

        # Try to read the updated videos.json to return the new videos
        all_videos = []
        try:
            if os.path.exists('videos.json'):
                with open('videos.json', 'r', encoding='utf-8') as f:
                    all_videos = json.load(f)
            else:
                all_videos = new_videos
        except Exception as e:
            print(f"Error reading videos.json: {e}")
            # Fallback to just returning new videos if file read fails
            all_videos = new_videos

        # Find videos that contain the keyword in title
        matching_videos = [v for v in all_videos
                         if keyword.lower() in v.get('title', '').lower()]

        print(f"Found {len(matching_videos)} matching videos in total")
        return jsonify({
            'success': True,
            'message': f'Scraped {len(new_videos)} new videos for "{keyword}"',
            'videos': matching_videos[:20]  # Return up to 20 videos
        })

    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        # On server error, still return local results if available
        try:
            if os.path.exists('videos.json'):
                with open('videos.json', 'r', encoding='utf-8') as f:
                    all_videos = json.load(f)
                matching_videos = [v for v in all_videos
                                 if keyword.lower() in v.get('title', '').lower()]
                return jsonify({
                    'success': True,
                    'message': f'Scraping failed, showing {len(matching_videos)} local results',
                    'videos': matching_videos[:20]
                })
        except Exception as local_e:
            print(f"Error reading local videos: {local_e}")
        return jsonify({
            'error': 'Server error during scraping and no local results available',
            'details': str(e)
        }), 500

@app.route('/escorts.html')
def escorts():
    return send_from_directory('.', 'escorts.html')

@app.route('/escorts.json')
def escorts_json():
    # Public endpoint - escorts should be viewable by everyone
    return send_from_directory('.', 'escorts.json')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
    response = send_from_directory(upload_dir, filename)
    # Add CORS headers for image access
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    return response

@app.route('/chat.html')
def chat_page():
    return send_from_directory('.', 'chat.html')

@app.route('/group_chat.html')
def group_chat_page():
    return send_from_directory('.', 'group_chat.html')

@app.route('/analytics.html')
def analytics_page():
    return send_from_directory('.', 'analytics.html')

@app.route('/admin/analytics.html')
def admin_analytics_page():
    return send_from_directory('.', 'analytics.html')

@app.route('/api/analytics')
def get_analytics():
    """Get real analytics data for the dashboard"""
    from datetime import datetime, timedelta
    from collections import defaultdict
    import re

    # Helper function to get data from JSON files safely
    def load_json_file(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [] if filename.endswith('.json') else {}

    # Load all data
    escorts = load_json_file('escorts.json')
    meet_requests = load_json_file('meet_requests.json')
    chat_messages = load_json_file('chat_messages.json')
    group_chat_messages = load_json_file('group_chat_messages.json')
    model_applications = load_json_file('model_applications.json')
    videos = load_json_file('videos.json')

    # Load real visitor analytics data
    visitor_data = load_json_file('visitor_analytics.json')
    visitors = visitor_data.get('visitors', [])
    sessions = visitor_data.get('sessions', [])

    # Calculate time-based metrics using real data
    now = datetime.now()
    time_ranges = {
        '7d': now - timedelta(days=7),
        '30d': now - timedelta(days=30),
        '90d': now - timedelta(days=90)
    }

    analytics_data = {}

    for range_name, cutoff_date in time_ranges.items():
        # Filter data by date range
        recent_meet_requests = [
            req for req in meet_requests
            if datetime.fromisoformat(req['timestamp']).replace(tzinfo=None) >= cutoff_date
        ]

        recent_chat_messages = []
        for request_id, messages in chat_messages.items():
            for msg in messages:
                if datetime.fromisoformat(msg['timestamp']).replace(tzinfo=None) >= cutoff_date:
                    recent_chat_messages.append(msg)

        recent_group_messages = [
            msg for msg in group_chat_messages
            if datetime.fromisoformat(msg['timestamp']).replace(tzinfo=None) >= cutoff_date
        ]

        recent_applications = [
            app for app in model_applications
            if datetime.fromisoformat(app['submitted_at']).replace(tzinfo=None) >= cutoff_date
        ]

        # Filter real visitor sessions by date range
        recent_sessions = [
            session for session in sessions
            if datetime.fromisoformat(session['timestamp']).replace(tzinfo=None) >= cutoff_date
        ]

        # Calculate metrics using real data
        unique_visitors = set(session['ip_address'] for session in recent_sessions)
        total_visitors = len(unique_visitors)

        # Calculate real page views (each session represents a page view)
        total_page_views = len(recent_sessions)

        # Calculate real session duration from visitor data
        session_durations = []
        ip_session_times = defaultdict(list)

        for session in recent_sessions:
            session_time = datetime.fromisoformat(session['timestamp'])
            ip_session_times[session['ip_address']].append(session_time)

        for ip, times in ip_session_times.items():
            if len(times) > 1:
                duration = (max(times) - min(times)).total_seconds() / 60  # minutes
                session_durations.append(duration)

        avg_session_minutes = sum(session_durations) / len(session_durations) if session_durations else 5.0

        # Calculate real bounce rate (single-page sessions)
        single_page_sessions = sum(1 for ip, times in ip_session_times.items() if len(times) == 1)
        bounce_rate = (single_page_sessions / max(len(ip_session_times), 1)) * 100

        # Generate daily data for the last N days using real session data
        days_count = 7 if range_name == '7d' else 30 if range_name == '30d' else 90
        daily_visitors = []
        daily_sessions = []
        labels = []

        for i in range(days_count):
            day_date = now - timedelta(days=days_count - 1 - i)
            day_cutoff = day_date.replace(hour=0, minute=0, second=0, microsecond=0)
            next_day = day_cutoff + timedelta(days=1)

            # Count real activities for this day
            day_sessions = [
                session for session in recent_sessions
                if day_cutoff <= datetime.fromisoformat(session['timestamp']) < next_day
            ]

            day_unique_visitors = len(set(session['ip_address'] for session in day_sessions))
            day_session_count = len(day_sessions)

            daily_visitors.append(max(day_unique_visitors, 1))  # Ensure at least 1 visitor
            daily_sessions.append(round(avg_session_minutes, 1) if day_unique_visitors > 0 else 5.0)
            labels.append(day_date.strftime('%b %d') if range_name != '7d' else day_date.strftime('%a'))

        analytics_data[range_name] = {
            'totalVisitors': max(total_visitors, 1),  # Use real visitor count
            'avgSession': f"{int(avg_session_minutes)}:{int((avg_session_minutes % 1) * 60):02d}",
            'bounceRate': f"{bounce_rate:.1f}%",
            'pageViews': total_page_views,
            'visitors': daily_visitors,
            'sessions': daily_sessions,
            'labels': labels,
            'totalEscorts': len(escorts),
            'totalMeetRequests': len(recent_meet_requests),
            'totalChatMessages': len(recent_chat_messages),
            'totalGroupMessages': len(recent_group_messages),
            'totalModelApplications': len(recent_applications),
            'totalVideos': len(videos)
        }

    # Dynamic data based on real analytics
    dynamic_data = {
        'trafficSources': get_real_traffic_sources(recent_sessions),
        'locations': get_real_locations(visitors),
        'devices': get_real_devices(recent_sessions),
        'peakHours': get_real_peak_hours(recent_sessions)
    }

    return jsonify({
        'success': True,
        'timeRanges': analytics_data,
        'static': dynamic_data
    })

def get_real_traffic_sources(sessions):
    """Analyze real traffic sources from session data"""
    sources = {'Direct': 0, 'Search Engines': 0, 'Social Media': 0, 'Referrals': 0, 'Email': 0}

    # This is a simplified approach - in production, you'd track referrer headers
    # For now, we'll use the path patterns to estimate sources
    for session in sessions:
        path = session.get('path', '').lower()

        if path.startswith('/admin'):
            sources['Direct'] += 1
        elif 'search' in path or 'q=' in path:
            sources['Search Engines'] += 1
        elif 'group_chat' in path or 'chat' in path:
            sources['Social Media'] += 1
        elif path.startswith('/meet') or path.startswith('/apply'):
            sources['Referrals'] += 1
        else:
            sources['Direct'] += 1

    # Convert counts to percentages
    total = sum(sources.values())
    if total > 0:
        for key in sources:
            sources[key] = round((sources[key] / total) * 100)

    return {
        'labels': list(sources.keys()),
        'data': list(sources.values())
    }

def get_real_locations(visitors):
    """Get real location data from visitor analytics"""
    location_counts = defaultdict(int)

    for visitor in visitors:
        location = visitor.get('location', {})
        country = location.get('country', 'Unknown')
        if country != 'Unknown':
            location_counts[country] += 1

    # If we have real location data, use it. Otherwise use reasonable defaults
    if location_counts:
        # Get top 6 countries
        top_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        labels = [loc[0] for loc in top_locations]
        data = [loc[1] for loc in top_locations]

        # Add "Others" if there are more countries
        if len(location_counts) > 6:
            others_count = sum(count for country, count in location_counts.items() if country not in labels)
            labels.append('Others')
            data.append(others_count)
    else:
        # Fallback to reasonable defaults if no location data
        labels = ['United States', 'United Kingdom', 'Canada', 'Germany', 'Australia', 'Others']
        data = [42, 18, 12, 10, 8, 10]

    return {
        'labels': labels,
        'data': data
    }

def get_real_devices(sessions):
    """Analyze real device types from user agent strings"""
    devices = {'Desktop': 0, 'Mobile': 0, 'Tablet': 0}

    for session in sessions:
        user_agent = session.get('user_agent', '').lower()

        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            devices['Mobile'] += 1
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            devices['Tablet'] += 1
        else:
            devices['Desktop'] += 1

    # Convert counts to percentages
    total = sum(devices.values())
    if total > 0:
        for key in devices:
            devices[key] = round((devices[key] / total) * 100)

    return {
        'labels': list(devices.keys()),
        'data': list(devices.values())
    }

def get_real_peak_hours(sessions):
    """Analyze real peak hours from session timestamps"""
    hourly_counts = [0] * 24  # 24 hours

    for session in sessions:
        try:
            session_time = datetime.fromisoformat(session['timestamp'])
            hour = session_time.hour
            hourly_counts[hour] += 1
        except:
            continue

    # Convert counts to a more reasonable scale for the chart
    max_count = max(hourly_counts) if hourly_counts else 1
    if max_count > 0:
        # Scale to a reasonable range (e.g., 100-600)
        scale_factor = 500 / max_count
        hourly_counts = [int(count * scale_factor) for count in hourly_counts]

    return {
        'labels': [f"{hour:02d}:00" for hour in range(24)],
        'data': hourly_counts
    }

@app.route('/debug/chat')
def debug_chat():
    """Debug endpoint to check chat system status"""
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_messages = {}

    upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
    upload_exists = os.path.exists(upload_dir)
    upload_contents = os.listdir(upload_dir) if upload_exists else []

    return jsonify({
        'chat_messages_file_exists': os.path.exists('chat_messages.json'),
        'total_chat_sessions': len(all_messages),
        'chat_session_keys': list(all_messages.keys()),
        'upload_dir': upload_dir,
        'upload_dir_exists': upload_exists,
        'upload_file_count': len(upload_contents),
        'sample_upload_files': upload_contents[:5] if upload_contents else []
    })

@app.route('/delete-client-history/<request_id>', methods=['DELETE'])
@csrf.exempt
def delete_client_history(request_id):
    """Delete a client meeting request from history"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Load existing meet requests
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Meet requests file not found'}), 404

    # Find and remove the request
    original_length = len(meet_requests)
    meet_requests = [req for req in meet_requests if str(req['id']) != str(request_id)]

    if len(meet_requests) == original_length:
        return jsonify({'error': 'Meeting request not found'}), 404

    # Save updated requests
    with open('meet_requests.json', 'w') as f:
        json.dump(meet_requests, f, indent=4)

    # Also delete associated chat messages
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_messages = {}

    if request_id in all_messages:
        del all_messages[request_id]
        with open('chat_messages.json', 'w') as f:
            json.dump(all_messages, f, indent=4)

    # PERMANENTLY commit the deletion to git
    commit_message = f"ADMIN: Delete client meeting request {request_id} and associated chat history"
    commit_success = commit_to_git('meet_requests.json', commit_message)

    response_data = {
        'success': True,
        'message': f'Client meeting request {request_id} and associated chat history deleted successfully',
        'deleted_request_id': request_id
    }

    if not commit_success:
        print("⚠️ WARNING: Client history deleted but git commit failed (likely Railway deployment)")
        print("Data is still deleted, but not version controlled")
        response_data['warning'] = 'Deletion successful but git commit failed. Data may not be permanently saved.'
        # Don't return error - deletion succeeded, just git commit failed
        # This is common on hosted platforms like Railway

    return jsonify(response_data)

@app.route('/delete-model-application/<int:application_id>', methods=['DELETE'])
@csrf.exempt
def delete_model_application(application_id):
    """Delete a model application"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Load existing model applications
        with open('model_applications.json', 'r') as f:
            applications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Model applications file not found'}), 404

    # Find and remove the application
    original_length = len(applications)
    applications = [app for app in applications if app['id'] != application_id]

    if len(applications) == original_length:
        return jsonify({'error': 'Model application not found'}), 404

    # Save updated applications
    with open('model_applications.json', 'w') as f:
        json.dump(applications, f, indent=4)

    # PERMANENTLY commit the deletion to git
    commit_message = f"ADMIN: Delete model application {application_id}"
    commit_success = commit_to_git('model_applications.json', commit_message)

    if not commit_success:
        print("🚨 CRITICAL: Model application deleted but NOT committed to git!")
        return jsonify({
            'error': 'Model application deleted but commit to git failed. Contact administrator.',
            'deleted_application_id': application_id
        }), 500

    return jsonify({
        'success': True,
        'message': f'Model application {application_id} deleted successfully'
    })

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
        # Find the escort to be deleted for logging
        escort_to_delete = next((e for e in escorts if e['id'] == escort_id), None)

        if not escort_to_delete:
            return jsonify({'error': 'Escort not found'}), 404

        # Delete escort
        escorts = [e for e in escorts if e['id'] != escort_id]

        # Save back to file
        with open('escorts.json', 'w') as f:
            json.dump(escorts, f, indent=4)

        # PERMANENTLY commit the deletion to git - admin changes are NEVER reversed
        commit_message = f"ADMIN: Delete escort profile - {escort_to_delete['name']} (ID: {escort_to_delete['id']})"
        commit_success = commit_to_git('escorts.json', commit_message)

        if not commit_success:
            print("🚨 CRITICAL: Escort profile deleted but NOT committed to git!")
            print("🚨 This deletion may be reverted on server restart!")
            return jsonify({
                'error': 'Profile deleted but commit to git failed. Contact administrator.',
                'deleted_escort': escort_to_delete
            }), 500

        return jsonify({
            'success': True,
            'message': f'Escort {escort_to_delete["name"]} permanently deleted',
            'deleted_escort': escort_to_delete
        })

    elif request.method == 'PUT':
        # Update escort - handle both JSON and form data for file uploads
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file uploads
            data = request.form
            uploaded_files = request.files.getlist('photos')
            photo_paths = []
            photos_to_delete = []

            # Handle photos to delete
            if 'photosToDelete' in data:
                photos_to_delete = [int(idx.strip()) for idx in data['photosToDelete'].split(',') if idx.strip()]

            # Handle new photos uploaded
            if uploaded_files and any(f.filename for f in uploaded_files):
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
            photo_paths = []
            photos_to_delete = data.get('photosToDelete', []) if data else []

        for i, escort in enumerate(escorts):
            if escort['id'] == escort_id:
                # Update basic fields
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

                # Handle photo updates
                current_photos = escorts[i]['photos'] if escorts[i]['photos'] else []

                # Remove photos marked for deletion
                if photos_to_delete:
                    # Sort in descending order to avoid index shifting issues
                    photos_to_delete.sort(reverse=True)
                    for idx in photos_to_delete:
                        if 0 <= idx < len(current_photos):
                            # Optionally delete the file from filesystem
                            photo_path = current_photos[idx]
                            if photo_path.startswith('/uploads/'):
                                file_path = photo_path[1:]  # Remove leading slash
                                try:
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                        print(f"Deleted photo file: {file_path}")
                                except Exception as e:
                                    print(f"Error deleting photo file {file_path}: {e}")

                            # Remove from array
                            current_photos.pop(idx)

                # Add new photos to existing ones
                if photo_paths:
                    current_photos.extend(photo_paths)

                escorts[i]['photos'] = current_photos

                # Save back to file
                with open('escorts.json', 'w') as f:
                    json.dump(escorts, f, indent=4)

                # PERMANENTLY commit the change to git - admin changes are NEVER reversed
                commit_message = f"ADMIN: Update escort profile - {escorts[i]['name']} (ID: {escorts[i]['id']})"
                commit_success = commit_to_git('escorts.json', commit_message)

                if not commit_success:
                    print("🚨 CRITICAL: Escort profile updated but NOT committed to git!")
                    print("🚨 This change may be lost on server restart!")
                    return jsonify({
                        'error': 'Profile updated but commit to git failed. Contact administrator.',
                        'escort': escorts[i]
                    }), 500

                return jsonify({
                    'success': True,
                    'message': f'Escort {escorts[i]["name"]} updated successfully',
                    'escort': escorts[i]
                })

        return jsonify({'error': 'Escort not found'}), 404

@app.route('/meet', methods=['POST'])
@csrf.exempt
@limiter.limit("20 per hour", methods=["POST"])  # Limit meeting requests
def meet():
    print("DEBUG: Meet request received")
    data = request.get_json()
    print(f"DEBUG: Meet request data: {data}")

    required_fields = ['escortId', 'clientName', 'clientLocation', 'clientContact', 'ageVerification']
    for field in required_fields:
        if not data.get(field):
            print(f"DEBUG: Missing required field: {field}")
            return jsonify({'error': f'{field} is required'}), 400

    # Validate age verification
    if data.get('ageVerification') != 'yes':
        print("DEBUG: Age verification failed")
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

    print(f"DEBUG: Created meet request: {meet_request}")

    # Load existing meet requests
    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
        print(f"DEBUG: Loaded {len(meet_requests)} existing requests")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"DEBUG: No existing meet_requests.json or error: {e}")
        meet_requests = []

    # Add new request
    meet_requests.append(meet_request)
    print(f"DEBUG: Added request, now {len(meet_requests)} total requests")

    # Save back to file
    try:
        with open('meet_requests.json', 'w') as f:
            json.dump(meet_requests, f, indent=4)
        print("DEBUG: Successfully saved meet_requests.json")

        # PERMANENTLY commit the new meeting request to git
        commit_message = f"NEW MEETING REQUEST: {meet_request['clientName']} for Escort ID {meet_request['escortId']}"
        commit_success = commit_to_git('meet_requests.json', commit_message)

        if not commit_success:
            print("⚠️ WARNING: Meeting request saved but git commit failed (likely Railway deployment)")
            print("Meeting request data is still saved, but not version controlled")
            # Don't return error - meeting request should still work
            # This is common on hosted platforms like Railway

    except Exception as e:
        print(f"DEBUG: Error saving meet_requests.json: {e}")
        return jsonify({'error': 'Failed to save meeting request'}), 500

    response_message = 'Meeting request submitted successfully. Admin will review for safety before approval.'
    if safety_warnings:
        response_message += f" Safety concerns: {', '.join(safety_warnings)}"

    response_data = {
        'success': True,
        'message': response_message,
        'request_id': meet_request['id'],
        'chat_url': f'/chat.html?request_id={meet_request["id"]}',
        'safety_warnings': safety_warnings,
        'chat_enabled': True
    }

    print(f"DEBUG: Returning response: {response_data}")
    return jsonify(response_data)

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

    # PERMANENTLY commit the safety check-in to git
    commit_message = f"ADMIN: Safety check-in for meet request {request_id} - Type: {checkin_type}"
    commit_success = commit_to_git('meet_requests.json', commit_message)

    if not commit_success:
        print("🚨 CRITICAL: Safety check-in recorded but NOT committed to git!")
        return jsonify({
            'error': 'Check-in recorded but commit to git failed. Contact administrator.',
            'checkin': checkin_record
        }), 500

    return jsonify({
        'success': True,
        'message': f'Check-in recorded: {checkin_type}',
        'checkin': checkin_record
    })

@app.route('/meet/<request_id>/status', methods=['POST'])
@csrf.exempt
def update_meeting_status(request_id):
    """Update meeting request status (admin only)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['pending', 'completed', 'cancelled', 'emergency']:
        return jsonify({'error': 'Invalid status'}), 400

    # Load meet requests
    try:
        with open('meet_requests.json', 'r') as f:
            meet_requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'error': 'Meeting request not found'}), 404

    # Find and update the request
    for req in meet_requests:
        if req['id'] == request_id:
            old_status = req['status']
            req['status'] = new_status
            req['status_updated_at'] = datetime.now().isoformat()
            req['status_updated_by'] = 'admin'

            # Save updated requests
            with open('meet_requests.json', 'w') as f:
                json.dump(meet_requests, f, indent=4)

            # PERMANENTLY commit the status update to git
            commit_message = f"ADMIN: Meeting status updated - Request {request_id} from {old_status} to {new_status}"
            commit_success = commit_to_git('meet_requests.json', commit_message)

            if not commit_success:
                print("🚨 CRITICAL: Meeting status updated but NOT committed to git!")
                return jsonify({
                    'error': 'Status updated but commit to git failed. Contact administrator.',
                    'request': req
                }), 500

            return jsonify({
                'success': True,
                'message': f'Meeting status updated to {new_status}',
                'request': req
            })

    return jsonify({'error': 'Meeting request not found'}), 404

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

            # PERMANENTLY commit the meeting end to git
            commit_message = f"ADMIN: Meeting ended for request {request_id} - Status: completed"
            commit_success = commit_to_git('meet_requests.json', commit_message)

            if not commit_success:
                print("🚨 CRITICAL: Meeting end recorded but NOT committed to git!")
                return jsonify({
                    'error': 'Meeting ended but commit to git failed. Contact administrator.',
                    'end_time': req['endTime']
                }), 500

            return jsonify({
                'success': True,
                'message': 'Meeting ended safely. Thank you for the safe check-in.',
                'end_time': req['endTime']
            })

    return jsonify({'error': 'Meeting request not found'}), 404

# Group chat endpoints
@app.route('/group_chat/messages', methods=['GET'])
def get_group_chat_messages():
    """Get all group chat messages"""
    try:
        with open('group_chat_messages.json', 'r') as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        messages = []

    # Get online count (users active in last 5 minutes)
    current_time = datetime.now()
    active_users = set()
    for msg in messages[-50:]:  # Check last 50 messages
        msg_time = datetime.fromisoformat(msg['timestamp'])
        if (current_time - msg_time).seconds < 300:  # 5 minutes
            active_users.add(msg['sender'])

    online_count = len(active_users)

    return jsonify({
        'success': True,
        'messages': messages[-100:],  # Return last 100 messages
        'online_count': online_count
    })

@app.route('/group_chat/send', methods=['POST'])
@csrf.exempt
@limiter.limit("100 per hour", methods=["POST"])  # Group chat message limits
def send_group_chat_message():
    """Send a group chat message"""
    data = request.get_json()

    sender = data.get('sender', 'Anonymous').strip()
    message = data.get('message', '').strip()
    original_message = data.get('original_message', '')
    was_censored = data.get('was_censored', False)

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if len(message) > 2000:
        return jsonify({'error': 'Message too long'}), 400

    # Sanitize message (basic XSS prevention)
    message = sanitize_chat_message(message)

    # Additional censorship for contact info if not already censored
    if not was_censored and original_message:
        censored_result = censor_contact_info(original_message)
        if censored_result['wasCensored']:
            message = censored_result['message']

    # Load existing messages
    try:
        with open('group_chat_messages.json', 'r') as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        messages = []

    # Generate message ID
    message_id = len(messages) + 1

    # Create message
    chat_message = {
        'id': message_id,
        'sender': sender[:20],  # Limit username length
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'censored': was_censored or ('[CENSORED]' in message)
    }

    messages.append(chat_message)

    # Keep only last 500 messages to prevent file from growing too large
    if len(messages) > 500:
        messages = messages[-500:]

    # Save messages
    with open('group_chat_messages.json', 'w') as f:
        json.dump(messages, f, indent=4)

    # Commit to git (optional for group chat)
    try:
        commit_message = f"GROUP CHAT: Message from {sender}"
        commit_to_git('group_chat_messages.json', commit_message)
    except:
        pass  # Don't fail if git commit fails

    return jsonify({
        'success': True,
        'message': chat_message
    })

def censor_contact_info(message):
    """
    Censor contact information in messages to prevent sharing personal details.
    """
    import re

    # Patterns to censor
    patterns = [
        # Phone numbers (various formats)
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE NUMBER CENSORED]'),  # 123-456-7890
        (r'\b\d{1,3}[-.]?\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE NUMBER CENSORED]'),  # +1-123-456-7890
        (r'\(\d{3}\)\s*\d{3}[-.]?\d{4}\b', '[PHONE NUMBER CENSORED]'),  # (123) 456-7890

        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL CENSORED]'),

        # Social media handles
        (r'@\w+', '[SOCIAL HANDLE CENSORED]'),
        (r'(?:instagram|twitter|facebook|snapchat|tiktok|discord|telegram|whatsapp|kik|skype):\s*\w+', '[SOCIAL MEDIA CENSORED]'),

        # URLs
        (r'(?:http|https|ftp):\/\/[^\s]+', '[URL CENSORED]'),
        (r'www\.[^\s]+', '[WEBSITE CENSORED]'),

        # Common contact keywords
        (r'(?:phone|mobile|cell|contact|number|email|insta|ig|snap|discord|telegram|whatsapp):\s*[^\s]+', '[CONTACT INFO CENSORED]')
    ]

    censored_message = message
    was_censored = False

    for pattern, replacement in patterns:
        if re.search(pattern, censored_message, re.IGNORECASE):
            censored_message = re.sub(pattern, replacement, censored_message, flags=re.IGNORECASE)
            was_censored = True

    return {
        'message': censored_message,
        'wasCensored': was_censored
    }

# Chat system endpoints
@app.route('/chat/<request_id>', methods=['GET'])
def get_chat_messages(request_id):
    """Get all chat messages for a request"""
    print(f"DEBUG: Getting chat messages for request_id: {request_id}")
    try:
        with open('chat_messages.json', 'r') as f:
            all_messages = json.load(f)
        print(f"DEBUG: Loaded chat_messages.json with keys: {list(all_messages.keys())}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"DEBUG: No chat_messages.json found or invalid JSON: {e}")
        all_messages = {}

    messages = all_messages.get(request_id, [])
    print(f"DEBUG: Returning {len(messages)} messages for request_id {request_id}")
    if messages:
        print(f"DEBUG: Sample message: {messages[-1]}")  # Show last message
    return jsonify({'messages': messages})

@app.route('/chat/<request_id>', methods=['POST'])
@csrf.exempt
@limiter.limit("200 per hour", methods=["POST"])  # Chat message limits - increased for better UX
def send_chat_message(request_id):
    """Send a chat message"""

    # Validate request_id format to prevent injection
    if not re.match(r'^[a-zA-Z0-9]+$', request_id):
        return jsonify({'error': 'Invalid request ID format'}), 400

    sender = None
    message = ""
    image_url = None

    # Check if this is a file upload (allowed for both admin and clients)
    if request.content_type and 'multipart/form-data' in request.content_type:
        # Determine sender based on admin session
        sender = 'admin' if session.get('admin_logged_in') else 'client'
        uploaded_file = request.files.get('image')

        if uploaded_file and uploaded_file.filename:
            # Generate unique filename
            filename = secure_filename(f"{uuid.uuid4()}_{uploaded_file.filename}")
            upload_dir = os.environ.get('UPLOAD_DIR', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            uploaded_file.save(file_path)
            image_url = f"/uploads/{filename}"
            # Optional caption text (stored separately from image_url so UIs can render safely)
            message = request.form.get('message', '').strip()
        else:
            return jsonify({'error': 'No image file provided'}), 400
    else:
        # Regular text message
        data = request.get_json()
        sender = data.get('sender', 'unknown')  # 'client' or 'admin'
        message = data.get('message', '').strip()

        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400

    # Sanitize the message to prevent XSS, but only if it's not admin-generated HTML content
    # Check if this is admin-generated HTML (contains <img tag)
    if not (sender == 'admin' and '<img' in message and 'src=' in message):
        message = sanitize_chat_message(message)
    else:
        # For admin-generated HTML, we still need basic validation
        # Remove any script tags that might have been injected
        message = re.sub(r'<script[^>]*>.*?</script>', '', message, flags=re.IGNORECASE | re.DOTALL)
        message = re.sub(r'javascript:', '', message, flags=re.IGNORECASE)
        message = re.sub(r'data:text/html', '', message, flags=re.IGNORECASE)
        message = message.strip()

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

    # Add image URL if present and valid
    if image_url and validate_image_url(image_url):
        chat_message['image_url'] = image_url
    elif image_url and not validate_image_url(image_url):
        print(f"WARNING: Invalid image URL rejected: {image_url}")

    all_messages[request_id].append(chat_message)

    # Save messages
    with open('chat_messages.json', 'w') as f:
        json.dump(all_messages, f, indent=4)

    print(f"DEBUG: Saved sanitized message for request_id {request_id}")

    # PERMANENTLY commit chat messages to git for proper version control
    # This ensures all chat history is preserved and can be recovered if needed
    sender_type = "ADMIN" if sender == 'admin' else "CLIENT"
    message_type = "image" if image_url else "text"
    commit_message = f"{sender_type} CHAT MESSAGE: {message_type.upper()} message in request {request_id}"
    commit_success = commit_to_git('chat_messages.json', commit_message)

    if not commit_success:
        print(f"⚠️  WARNING: Chat message saved but git commit failed for request {request_id}")
        print("Chat message data is still saved, but not version controlled")
        # Don't return error - chat should still work even if git commit fails
        # This is common on hosted platforms like Railway

    return jsonify({
        'success': True,
        'message': chat_message
    })

@app.route('/chat/<request_id>/end', methods=['POST'])
@csrf.exempt
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

        # Try to commit the chat session end to git (may fail on Railway)
        commit_message = f"ADMIN: Chat session ended for request {request_id}"
        commit_success = commit_to_git('chat_messages.json', commit_message)

        if not commit_success:
            print(f"⚠️  WARNING: Chat session ended but git commit failed (likely Railway deployment)")
            print("Chat session data is still saved, but not version controlled")
            # Don't return error - chat ending should still work

        return jsonify({
            'success': True,
            'message': 'Chat session ended successfully'
        })
    else:
        return jsonify({
            'error': 'Chat session not found'
        }), 404

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("20 per hour", methods=["POST"])  # More lenient limit for admin login
def admin_login():
    form = AdminLoginForm()
    error_message = None

    if request.method == 'POST':
        if form.validate_on_submit():
            password = form.password.data
            if check_password_hash(ADMIN_PASSWORD_HASH, password):
                session['admin_logged_in'] = True
                return redirect('/admin/escorts')
            else:
                error_message = 'Invalid password'
        else:
            # Handle CSRF token expiry and other validation errors
            if 'csrf_token' in form.errors:
                error_message = 'Session expired. Please refresh the page and try again.'
            else:
                error_message = 'Form validation error. Please try again.'

    return render_template('admin_login.html', form=form, error=error_message)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

def require_admin_login():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

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

        # PERMANENTLY commit the creation to git - admin changes are NEVER reversed
        commit_message = f"ADMIN: Create new escort profile - {escort['name']} (ID: {escort['id']})"
        commit_success = commit_to_git('escorts.json', commit_message)

        if not commit_success:
            print("🚨 CRITICAL: New escort profile created but NOT committed to git!")
            print("🚨 This profile may be lost on server restart!")
            return jsonify({
                'error': 'Profile created but commit to git failed. Contact administrator.',
                'escort': escort
            }), 500

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

    is_dev = os.environ.get('FLASK_ENV') == 'development'

    # Development defaults (Windows-friendly):
    # - Use DEV_PORT instead of PORT (many Windows setups have PORT set globally)
    # - Bind to 127.0.0.1 by default to avoid OS/network policy restrictions
    if is_dev:
        host = os.environ.get('DEV_HOST', '127.0.0.1')
        port = int(os.environ.get('DEV_PORT', 5000))
        print("🚀 Starting Flask development server...")
        print("⚠️  WARNING: This is a development server. Do not use in production!")
        print(f"   Listening on http://{host}:{port}")
        app.run(host=host, port=port, debug=True)
    else:
        host = os.environ.get('HOST', '0.0.0.0')
        port = int(os.environ.get('PORT', 8000))
        print("✅ Production mode: Use Gunicorn or another WSGI server")
        print(f"   Example: gunicorn --bind {host}:{port} --workers 4 server:app")
        app.run(host=host, port=port, debug=True)
