from flask import Flask, request, jsonify, send_from_directory, render_template, session, redirect
import subprocess
import sys
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid

# Import shuffle functionality
try:
    from scraper import start_shuffle_scheduler, shuffle_videos
    SHUFFLE_AVAILABLE = True
except ImportError:
    SHUFFLE_AVAILABLE = False
    print("Warning: Shuffle functionality not available (scraper.py not found)")

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_production'

# Hashed admin password - in production, use proper authentication
ADMIN_PASSWORD_HASH = generate_password_hash("passhavok")

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

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400

    try:
        # Run the scraper with the keyword
        result = subprocess.run([sys.executable, 'scraper.py', keyword],
                              capture_output=True, text=True, cwd=os.getcwd())

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
    return send_from_directory('.', 'escorts.json')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

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
                        file_path = os.path.join('uploads', filename)
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
def meet():
    data = request.get_json()

    required_fields = ['escortId', 'clientName', 'clientLocation', 'clientContact']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Create meet request
    meet_request = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S'),
        'escortId': data['escortId'],
        'clientName': data['clientName'],
        'clientLocation': data['clientLocation'],
        'clientContact': data['clientContact'],
        'meetingDetails': data.get('meetingDetails', ''),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending'
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

    return jsonify({
        'success': True,
        'message': 'Meeting request submitted successfully. Admin will contact you soon.',
        'request_id': meet_request['id']
    })

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect('/admin/escorts')
        else:
            return render_template('admin_login.html', error='Invalid password')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

def require_admin_login():
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')

@app.route('/admin/escorts', methods=['GET', 'POST'])
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
                file_path = os.path.join('uploads', filename)
                file.save(file_path)
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

    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
