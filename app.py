import eventlet
eventlet.monkey_patch()

from flask import Flask
from config import Config
from extensions import db, login_manager, socketio

def create_app():
    app = Flask(__name__, static_folder='static')
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    socketio.init_app(app, async_mode='eventlet')
    
    with app.app_context():
        from models import User, Message, PrivateMessage
        db.create_all()
    
    from routes import main
    app.register_blueprint(main)
    
    return app

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=false)
