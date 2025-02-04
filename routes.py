import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, socketio
from models import User, Message, PrivateMessage
from forms import RegistrationForm, LoginForm, MessageForm
from flask_socketio import emit, join_room
from sqlalchemy import or_, and_

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
        hashed = generate_password_hash(form.password.data)
        user = User(username=form.username.data, password=hashed)
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
            if user.logged_in:
                flash('This user is already logged in from another device. Please log out from that device first.', 'danger')
                return redirect(url_for('main.login'))
            login_user(user)
            user.logged_in = True
            db.session.commit()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('main.common_chat'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html', form=form)

@main.route('/logout')
@login_required
def logout():
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
    return render_template('common_chat.html', form=form, messages=messages)

@main.route('/personal_chat/<username>', methods=['GET'])
@login_required
def personal_chat(username):
    other = User.query.filter_by(username=username).first()
    if not other:
        flash('User not found.', 'danger')
        return redirect(url_for('main.common_chat'))
    form = MessageForm()
    messages = PrivateMessage.query.filter(
        or_(
            and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.recipient_id == other.id),
            and_(PrivateMessage.sender_id == other.id, PrivateMessage.recipient_id == current_user.id)
        )
    ).order_by(PrivateMessage.timestamp.asc()).all()
    return render_template('personal_chat.html', form=form, messages=messages, recipient=other)

@main.route('/personal_chats', methods=['GET'])
@login_required
def personal_chats():
    msgs = PrivateMessage.query.filter(
        or_(PrivateMessage.sender_id == current_user.id, PrivateMessage.recipient_id == current_user.id)
    ).all()
    contact_ids = set()
    for m in msgs:
        if m.sender_id != current_user.id:
            contact_ids.add(m.sender_id)
        if m.recipient_id != current_user.id:
            contact_ids.add(m.recipient_id)
    contacts = User.query.filter(User.id.in_(list(contact_ids))).all()
    return render_template('personal_chats.html', contacts=contacts)

# --- Socket.IO Events ---

@socketio.on('send_message')
def handle_send_message_event(data):
    msg_text = data.get('message')
    username = data.get('username')
    print(f"[DEBUG] Received message from {username}: '{msg_text}'")
    user = User.query.filter_by(username=username).first()
    if user and msg_text.strip():
        message = Message(user_id=user.id, username=user.username, message=msg_text)
        db.session.add(message)
        db.session.commit()
        emit('receive_message', {
            'message': msg_text,
            'username': username,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M')
        }, broadcast=True)
    else:
        emit('error', {'error': 'Invalid message or user.'})

@socketio.on('join_user')
def on_join_user(data):
    username = data.get('username')
    if username:
        room = "user_" + username
        join_room(room)
        print(f"[DEBUG] {username} joined room {room}")

@socketio.on('send_private_message')
def handle_send_private_message_event(data):
    msg_text = data.get('message')
    sender_username = data.get('sender')
    recipient_username = data.get('recipient')
    print(f"[DEBUG] Received private message from {sender_username} to {recipient_username}: '{msg_text}'")
    sender = User.query.filter_by(username=sender_username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if sender and recipient and msg_text.strip():
        private_msg = PrivateMessage(sender_id=sender.id, recipient_id=recipient.id, message=msg_text)
        db.session.add(private_msg)
        db.session.commit()
        room = 'private_' + '_'.join(map(str, sorted([sender.id, recipient.id])))
        emit('receive_private_message', {
            'message': msg_text,
            'sender': sender_username,
            'timestamp': private_msg.timestamp.strftime('%Y-%m-%d %H:%M')
        }, room=room)
    else:
        emit('error', {'error': 'Invalid private message data.'})

@socketio.on('join_private')
def on_join_private(data):
    sender_username = data.get('sender')
    recipient_username = data.get('recipient')
    sender = User.query.filter_by(username=sender_username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if sender and recipient:
        room = 'private_' + '_'.join(map(str, sorted([sender.id, recipient.id])))
        join_room(room)
        print(f"[DEBUG] {sender_username} joined private room {room}")
        emit('status', {'msg': f'{sender_username} has joined the private chat.'}, room=room)
    else:
        emit('error', {'error': 'Invalid sender or recipient for private chat.'})
