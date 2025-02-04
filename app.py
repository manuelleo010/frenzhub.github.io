import os
import uuid
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.utils import secure_filename

from models import db, User

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, manage_session=False)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# Helper to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ---------------------------
# Session management: Check for inactivity (15 minutes)
# ---------------------------
@app.before_request
def session_management():
    session.permanent = True
    now = datetime.utcnow()
    if 'last_activity' in session:
        last = datetime.strptime(session['last_activity'], '%Y-%m-%d %H:%M:%S')
        if (now - last).total_seconds() > 15 * 60:
            # Clear the user's active session in the database if they exist.
            if 'username' in session:
                user = User.query.filter_by(username=session['username']).first()
                if user:
                    user.active_session = None
                    db.session.commit()
            session.clear()
            flash("Session expired due to inactivity", "info")
            return redirect(url_for('login'))
    session['last_activity'] = now.strftime('%Y-%m-%d %H:%M:%S')

# ---------------------------
# ROUTES
# ---------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        # Check if the username is already taken.
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for('register'))
        # Create new user
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or user.password != password:
            flash("Invalid credentials", "danger")
            return redirect(url_for('login'))
        # Check if the user is already logged in elsewhere.
        if user.active_session:
            flash("User already logged in from another device", "danger")
            return redirect(url_for('login'))
        # Successful login: store username and a unique session id.
        session['username'] = username
        session['sid'] = str(uuid.uuid4())
        user.active_session = session['sid']
        db.session.commit()
        flash("Successfully logged in", "success")
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    username = session.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            user.active_session = None
            db.session.commit()
    session.clear()
    return redirect(url_for('login'))

# Endpoint for file uploads (images and videos)
@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        file_url = url_for('static', filename=f'uploads/{unique_filename}')
        room = request.form.get('room', 'common')
        # Broadcast a message with the file URL so that clients can display the image/video.
        socketio.emit('message', {
            'msg': f"{session['username']} sent an attachment",
            'file_url': file_url
        }, room=room)
        return jsonify({'success': True, 'file_url': file_url})
    else:
        return jsonify({'error': 'File type not allowed'}), 400

# ---------------------------
# SOCKETIO EVENTS
# ---------------------------
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('message', {
        'msg': f"{session.get('username', 'Someone')} has entered the room."
    }, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    emit('message', {
        'msg': f"{session.get('username', 'Someone')} has left the room."
    }, room=room)

@socketio.on('text')
def text(data):
    room = data.get('room', 'common')
    message = data.get('msg', '')
    # Broadcast text message to all users in the room.
    emit('message', {
        'msg': f"{session.get('username', 'Anonymous')}: {message}"
    }, room=room)

@socketio.on('disconnect')
def on_disconnect():
    username = session.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            user.active_session = None
            db.session.commit()

# ---------------------------
# MAIN
# ---------------------------
if __name__ == '__main__':
    # Ensure the uploads folder exists.
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Run the application with SocketIO (using eventlet)
    socketio.run(app, debug=True)
