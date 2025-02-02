import eventlet
eventlet.monkey_patch()

import threading
import time
import datetime
from flask import Flask
from config import Config
from extensions import db, login_manager, socketio

def create_app():
    app = Flask(__name__, static_folder='static')
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    socketio.init_app(app, async_mode='eventlet')
    
    # Create database tables if they do not exist
    with app.app_context():
        from models import User, Message, PrivateMessage
        db.create_all()
    
    # Register blueprints
    from routes import main
    app.register_blueprint(main)
    
    return app

def delete_old_messages(app):
    """
    Runs in a background thread and deletes messages whose 'read_at' timestamp
    is older than 24 hours.
    """
    while True:
        time.sleep(60)  # Run every minute
        with app.app_context():
            now = datetime.datetime.utcnow()
            threshold = now - datetime.timedelta(hours=24)
            from models import Message, PrivateMessage
            common_messages = Message.query.filter(
                Message.read_at != None, Message.read_at < threshold
            ).all()
            for msg in common_messages:
                db.session.delete(msg)
            private_messages = PrivateMessage.query.filter(
                PrivateMessage.read_at != None, PrivateMessage.read_at < threshold
            ).all()
            for msg in private_messages:
                db.session.delete(msg)
            db.session.commit()
            print("[DEBUG] Deleted old messages.")


app = create_app()
if __name__ == '__main__':
   
    # Start background thread to delete old messages.
    thread = threading.Thread(target=delete_old_messages, args=(app,), daemon=True)
    thread.start()
    socketio.run(app, debug=True)
