from flask import Flask
from flask_cors import CORS
# from config import Config

# def create_app(config_class=Config):
def create_app():
    app = Flask(__name__)
    # app.config.from_object(config_class)
    CORS(app)

    from app.routes.nutrition_prediction import pred_bp
    from app.routes.nutrition_tracking import track_bp
    
    app.register_blueprint(pred_bp, url_prefix='/api/prediction')
    app.register_blueprint(track_bp, url_prefix='/api/tracking')

    return app
