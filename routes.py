from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, socketio
from models import User, Message, PrivateMessage
from forms import RegistrationForm, LoginForm, MessageForm
from flask_socketio import emit, join_room
from sqlalchemy import or_, and_
import datetime

main = Blueprint('main', __name__)

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
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.common_chat'))
        else:
            flash('Login unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/common_chat', methods=['GET'])
@login_required
def common_chat():
    form = MessageForm()
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    # Mark messages as read if not from the current user.
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
    # Mark messages as read (if not sent by the current user)
    now = datetime.datetime.utcnow()
    updated = False
    for msg in messages:
        # Only mark as read if the current user did not send it
        if msg.sender_id != current_user.id and msg.read_at is None:
            msg.read_at = now
            updated = True
    if updated:
        db.session.commit()
    return render_template('personal_chat.html', form=form, messages=messages, recipient=recipient)

# Socket.IO event: When a client connects, they join their personal room.
@socketio.on('join_user')
def on_join_user(data):
    username = data.get('username')
    if username:
        room = "user_" + username
        join_room(room)
        print(f"[DEBUG] User {username} joined room {room}.")

# Socket.IO event for common chat messages.
@socketio.on('send_message')
def handle_send_message_event(data):
    msg_text = data.get('message')
    username = data.get('username')
    print(f"[DEBUG] Received common message from {username}: {msg_text}")
    user = User.query.filter_by(username=username).first()
    if user and msg_text:
        message = Message(user_id=user.id, username=user.username, message=msg_text)
        db.session.add(message)
        db.session.commit()
        emit('receive_message', {
            'message': msg_text,
            'username': username,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M')
        }, broadcast=True)
    else:
        print("[DEBUG] Error in send_message: invalid message or user")
        emit('error', {'error': 'Invalid message or user.'})

# Socket.IO event for private chat messages.
@socketio.on('send_private_message')
def handle_send_private_message_event(data):
    msg_text = data.get('message')
    sender_username = data.get('sender')
    recipient_username = data.get('recipient')
    print(f"[DEBUG] Received private message from {sender_username} to {recipient_username}: {msg_text}")
    sender = User.query.filter_by(username=sender_username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if sender and recipient and msg_text:
        private_msg = PrivateMessage(sender_id=sender.id, recipient_id=recipient.id, message=msg_text)
        db.session.add(private_msg)
        db.session.commit()
        room = get_private_room(sender.id, recipient.id)
        emit('receive_private_message', {
            'message': msg_text,
            'sender': sender_username,
            'timestamp': private_msg.timestamp.strftime('%Y-%m-%d %H:%M')
        }, room=room)
        # Also, send a private message request to the recipient’s personal room.
        emit('private_message_request', {
            'message': msg_text,
            'sender': sender_username,
            'timestamp': private_msg.timestamp.strftime('%Y-%m-%d %H:%M')
        }, room="user_" + recipient.username)
    else:
        print("[DEBUG] Error in send_private_message: invalid data")
        emit('error', {'error': 'Invalid message, sender, or recipient.'})

# Socket.IO event for joining a private chat room.
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

# Socket.IO event for rejecting a private chat request.
@socketio.on('reject_private_message')
def handle_reject_private_message(data):
    # 'sender' is the user rejecting (the recipient) and 'recipient' is the original sender.
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
    """Generate a unique room name based on two user IDs (order independent)."""
    return 'private_' + '_'.join(map(str, sorted([user1_id, user2_id])))
