import os
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from extensions import db, socketio
from models import User, Message, PrivateMessage
from forms import RegistrationForm, LoginForm, MessageForm
from flask_socketio import emit, join_room
from sqlalchemy import or_, and_

main = Blueprint('main', __name__)

# --------------------
# Helper function for media uploads
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/personal_chats', methods=['GET'])
@login_required
def personal_chats():
    # Get all private messages involving the current user.
    messages = PrivateMessage.query.filter(
        or_(
            PrivateMessage.sender_id == current_user.id,
            PrivateMessage.recipient_id == current_user.id
        )
    ).all()
    # Build a set of user IDs that are in conversation with current_user.
    contact_ids = set()
    for msg in messages:
        if msg.sender_id != current_user.id:
            contact_ids.add(msg.sender_id)
        if msg.recipient_id != current_user.id:
            contact_ids.add(msg.recipient_id)
    # Query the User table for these IDs.
    contacts = User.query.filter(User.id.in_(contact_ids)).all()
    # Render a new template listing these contacts.
    return render_template('personal_chats.html', contacts=contacts)


# Route to handle media upload via AJAX.
@main.route('/upload_media', methods=['POST'])
@login_required
def upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        # Ensure the folder exists.
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        file_url = url_for('static', filename='uploads/' + filename)
        # Determine file type:
        ext = filename.rsplit('.', 1)[1].lower()
        if ext in ['jpg', 'jpeg', 'png', 'gif']:
            file_type = 'image'
        else:
            file_type = 'video'
        return jsonify({'file_url': file_url, 'file_type': file_type})
    return jsonify({'error': 'File type not allowed'}), 400

# --------------------
@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.common_chat'))
    return redirect(url_for('main.login'))

@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.common_chat'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.common_chat'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            # Prevent simultaneous login: if already logged in, reject the new login.
            if user.logged_in:
                flash('This user is already logged in from another device. Please log out from that device first.', 'danger')
                return redirect(url_for('main.login'))
            login_user(user)
            user.logged_in = True  # Mark the user as logged in
            db.session.commit()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('main.common_chat'))
        else:
            flash('Login unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

@main.route('/logout')
@login_required
def logout():
    # Mark the user as logged out before logging out
    current_user.logged_in = False
    db.session.commit()
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))

@main.route('/common_chat', methods=['GET'])
@login_required
def common_chat():
    form = MessageForm()
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    now = datetime.datetime.utcnow()
    updated = False
    for msg in messages:
        if msg.username != current_user.username and msg.read_at is None:
            msg.read_at = now
            updated = True
    if updated:
        db.session.commit()
    return render_template('common_chat.html', form=form, messages=messages)

@main.route('/personal_chat/<username>', methods=['GET'])
@login_required
def personal_chat(username):
    recipient = User.query.filter_by(username=username).first()
    if not recipient:
        flash('User not found.', 'danger')
        return redirect(url_for('main.common_chat'))
    form = MessageForm()
    messages = PrivateMessage.query.filter(
        or_(
            and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.recipient_id == recipient.id),
            and_(PrivateMessage.sender_id == recipient.id, PrivateMessage.recipient_id == current_user.id)
        )
    ).order_by(PrivateMessage.timestamp.asc()).all()
    now = datetime.datetime.utcnow()
    updated = False
    for msg in messages:
        if msg.sender_id != current_user.id and msg.read_at is None:
            msg.read_at = now
            updated = True
    if updated:
        db.session.commit()
    return render_template('personal_chat.html', form=form, messages=messages, recipient=recipient)

# --------------------
# Socket.IO events remain largely as before, with added support for media fields.
@socketio.on('join_user')
def on_join_user(data):
    username = data.get('username')
    if username:
        room = "user_" + username
        join_room(room)
        print(f"[DEBUG] User {username} joined room {room}.")

@socketio.on('send_message')
def handle_send_message_event(data):
    msg_text = data.get('message')
    username = data.get('username')
    file_url = data.get('file_url')  # May be None
    file_type = data.get('file_type')  # May be None
    print(f"[DEBUG] Received common message from {username}: {msg_text} | file: {file_url}")
    user = User.query.filter_by(username=username).first()
    if user and (msg_text or file_url):
        message = Message(user_id=user.id, username=user.username, message=msg_text,
                          file_url=file_url, file_type=file_type)
        db.session.add(message)
        db.session.commit()
        emit('receive_message', {
            'message': msg_text,
            'username': username,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M'),
            'file_url': file_url,
            'file_type': file_type
        }, broadcast=True)
    else:
        print("[DEBUG] Error in send_message: invalid message or user")
        emit('error', {'error': 'Invalid message or user.'})

@socketio.on('send_private_message')
def handle_send_private_message_event(data):
    msg_text = data.get('message')
    sender_username = data.get('sender')
    recipient_username = data.get('recipient')
    file_url = data.get('file_url')
    file_type = data.get('file_type')
    print(f"[DEBUG] Received private message from {sender_username} to {recipient_username}: {msg_text} | file: {file_url}")
    sender = User.query.filter_by(username=sender_username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if sender and recipient and (msg_text or file_url):
        private_msg = PrivateMessage(sender_id=sender.id, recipient_id=recipient.id, message=msg_text,
                                       file_url=file_url, file_type=file_type)
        db.session.add(private_msg)
        db.session.commit()
        room = get_private_room(sender.id, recipient.id)
        emit('receive_private_message', {
            'message': msg_text,
            'sender': sender_username,
            'timestamp': private_msg.timestamp.strftime('%Y-%m-%d %H:%M'),
            'file_url': file_url,
            'file_type': file_type
        }, room=room)
        emit('private_message_request', {
            'message': msg_text,
            'sender': sender_username,
            'timestamp': private_msg.timestamp.strftime('%Y-%m-%d %H:%M'),
            'file_url': file_url,
            'file_type': file_type
        }, room="user_" + recipient.username)
    else:
        print("[DEBUG] Error in send_private_message: invalid data")
        emit('error', {'error': 'Invalid message, sender, or recipient.'})

@socketio.on('join_private')
def on_join_private(data):
    sender_username = data.get('sender')
    recipient_username = data.get('recipient')
    print(f"[DEBUG] {sender_username} attempting to join private chat with {recipient_username}")
    sender = User.query.filter_by(username=sender_username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if sender and recipient:
        room = get_private_room(sender.id, recipient.id)
        join_room(room)
        print(f"[DEBUG] {sender_username} joined room {room}")
        emit('status', {'msg': f'{sender_username} has joined the private chat.'}, room=room)
    else:
        print("[DEBUG] Error in join_private: invalid sender or recipient")
        emit('error', {'error': 'Invalid sender or recipient.'})

@socketio.on('reject_private_message')
def handle_reject_private_message(data):
    rejecting_user = data.get('sender')
    original_sender = data.get('recipient')
    print(f"[DEBUG] {rejecting_user} rejected private chat from {original_sender}")
    rejecter = User.query.filter_by(username=rejecting_user).first()
    sender = User.query.filter_by(username=original_sender).first()
    if rejecter and sender:
        room = get_private_room(rejecter.id, sender.id)
        emit('private_chat_rejected', {'msg': f"{rejecting_user} has rejected your private chat request."}, room=room)
    else:
        emit('error', {'error': 'Error processing rejection.'})

def get_private_room(user1_id, user2_id):
    return 'private_' + '_'.join(map(str, sorted([user1_id, user2_id])))
