from datetime import datetime
from extensions import db, login_manager
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    # Indicates whether the user is currently logged in
    logged_in = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=True)  # May be empty if media-only
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    # Optional media fields:
    file_url = db.Column(db.String(256), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)  # e.g. "image", "video"
    
    def __repr__(self):
        return f'<Message {self.message or "[Media]"}>'

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    # Optional media fields:
    file_url = db.Column(db.String(256), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    
    def __repr__(self):
        return f'<PrivateMessage {self.message or "[Media]"}>'
