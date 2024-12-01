from flask import Blueprint, request, jsonify
import pandas as pd
import os
from datetime import datetime
from app.routes.nutrition_prediction import predict_nutrition

track_bp = Blueprint('tracking', __name__)

# Load food database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df_food = pd.read_csv(os.path.join(BASE_DIR, 'data/data_baby_food.csv'))

"""
TODO: Database Integration
- Create tables: food_tracking, daily_nutrition
- Add user authentication
- Store tracking data per user
- Add proper indexing for date and user_id
"""

# In-memory storage untuk tracking data
daily_tracking = {}

@track_bp.route('/initialize-tracking', methods=['POST'])
def initialize_tracking():
    """
    Inisialisasi tracking nutrisi untuk user ketika memulai hari.
    
    Request Body:
    {
        "user_id": str,
        "usia_bulan": int,
        "gender": str, // L atau P
        "berat_kg": float,
        "tinggi_cm": float,
        "aktivitas_level": str, // Rendah, Sedang, Aktif, Sangat_Aktif 
        "status_asi": str // ASI_Eksklusif, ASI+MPASI, MPASI
    }
    
    Returns:
        JSON dengan predicted needs dan status inisialisasi
    """
    try:
        data = request.get_json()
        
        # Validasi input
        required_fields = ['user_id', 'usia_bulan', 'gender', 'berat_kg', 
                         'tinggi_cm', 'aktivitas_level', 'status_asi']
        if not all(field in data for field in required_fields):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400

        # Setup prediction parameters
        prediction_params = {
            "age": data['usia_bulan'],
            "weight": data['berat_kg'],
            "gender": data['gender'],
            "height": data['tinggi_cm'],
            "activity": data['aktivitas_level'],
            "asi_status": data['status_asi']
        }
        
        # Get nutrition prediction
        predicted_needs = predict_nutrition(prediction_params)
        
        # Initialize tracking data
        if data['user_id'] not in daily_tracking:
            daily_tracking[data['user_id']] = {}
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        daily_tracking[data['user_id']][current_date] = {
            'predicted_needs': predicted_needs,
            'total_nutrients': {
                'calories': 0,
                'proteins': 0,
                'fat': 0,
                'carbohydrate': 0,
                'calcium': 0
            },
            'foods': []
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'predicted_needs': predicted_needs,
                'tracking_initialized': True
            }
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@track_bp.route('/add-food', methods=['POST'])
def add_food():
    """
    Menambahkan makanan ke tracking harian dan melakukan evaluasi nutrisi.
    
    Request Body:
    {
        "user_id": str,
        "food_name": str,
        "date": "YYYY-MM-DD",
        "portion": float
    }
    
    Returns:
        JSON dengan data tracking updated dan evaluasi nutrisi
    """
    try:
        data = request.get_json()
        
        # Validasi input
        required_fields = ['user_id', 'food_name', 'date', 'portion']
        if not all(field in data for field in required_fields):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400

        user_id = data['user_id']
        food_name = data['food_name']
        date = data['date']
        portion = float(data['portion'])

        # Validasi format tanggal
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400

        # Validasi portion
        if portion <= 0:
            return jsonify({
                'status': 'error',
                'message': 'Portion must be greater than 0'
            }), 400

        # Cari makanan di database
        food_data = df_food[df_food['Food (per 100g)'].str.strip().str.lower() == food_name.strip().lower()]
        
        if food_data.empty:
            return jsonify({
                'status': 'error',
                'message': f"Food '{food_name}' not found in database"
            }), 400

        # Update tracking data
        if user_id not in daily_tracking:
            daily_tracking[user_id] = {}
            
        if date not in daily_tracking[user_id]:
            daily_tracking[user_id][date] = {
                'total_nutrients': {
                    'calories': 0,
                    'calcium': 0,
                    'proteins': 0,
                    'fat': 0,
                    'carbohydrate': 0
                },
                'foods': []
            }

        # Calculate nutrients
        food_row = food_data.iloc[0]
        food_nutrients = {
            'calories': food_row['Calorie(kcal)'] * portion/100,
            'calcium': food_row['Calcium(mg)'] * portion/100,
            'proteins': food_row['Protein(g)'] * portion/100,
            'fat': food_row['Fat(g)'] * portion/100,
            'carbohydrate': food_row['Carbohydrate(g)'] * portion/100
        }

        # Update total nutrients
        for nutrient in food_nutrients:
            daily_tracking[user_id][date]['total_nutrients'][nutrient] += food_nutrients[nutrient]

        # Add food to list
        daily_tracking[user_id][date]['foods'].append({
            'name': food_name,
            'portion': portion,
            'nutrients': food_nutrients,
            'notes': food_row['Notes']
        })

        # Evaluate nutrition if predicted needs exist
        if 'predicted_needs' in daily_tracking[user_id][date]:
            evaluation = evaluate_nutrition(
                daily_tracking[user_id][date]['predicted_needs'],
                daily_tracking[user_id][date]['total_nutrients']
            )
            
            return jsonify({
                'status': 'success',
                'data': {
                    'tracking': daily_tracking[user_id][date],
                    'evaluation': evaluation
                }
            }), 200

        return jsonify({
            'status': 'success',
            'data': daily_tracking[user_id][date]
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@track_bp.route('/get-daily/<user_id>/<date>', methods=['GET'])
def get_daily(user_id, date):
    """
    Mendapatkan data tracking dan evaluasi nutrisi harian.
    
    Parameters:
        user_id (str): ID user
        date (str): Tanggal dalam format YYYY-MM-DD
    
    Returns:
        JSON dengan data tracking dan evaluasi nutrisi
    """
    try:
        # Validasi format tanggal
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400

        if user_id not in daily_tracking or date not in daily_tracking[user_id]:
            return jsonify({
                'status': 'error',
                'message': 'No tracking data found'
            }), 404

        tracking_data = daily_tracking[user_id][date]
        
        # Add evaluation if predicted needs exist
        if 'predicted_needs' in tracking_data:
            evaluation = evaluate_nutrition(
                tracking_data['predicted_needs'],
                tracking_data['total_nutrients']
            )
            
            return jsonify({
                'status': 'success',
                'data': {
                    'tracking': tracking_data,
                    'evaluation': evaluation
                }
            }), 200

        return jsonify({
            'status': 'success',
            'data': tracking_data
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def evaluate_nutrition(predicted, consumed):
    """
    Helper function untuk mengevaluasi nutrisi.
    
    Parameters:
        predicted (dict): Predicted nutritional needs
        consumed (dict): Consumed nutrients
    
    Returns:
        dict: Evaluation results
    """
    evaluation = {}
    for nutrient in ['calories', 'proteins', 'fat', 'carbohydrate']:
        if nutrient not in predicted:
            continue
            
        consumed_amount = consumed[nutrient]
        predicted_amount = predicted[nutrient]
        percentage = (consumed_amount / predicted_amount * 100) if predicted_amount > 0 else 0
        
        evaluation[nutrient] = {
            'consumed': round(consumed_amount, 2),
            'predicted_needed': round(predicted_amount, 2),
            'percentage': round(percentage, 1),
            'status': 'adequate' if 90 <= percentage <= 110 else 'low' if percentage < 90 else 'high'
        }
    
    return evaluation