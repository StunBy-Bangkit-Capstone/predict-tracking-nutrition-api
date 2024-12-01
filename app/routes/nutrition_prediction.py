from flask import Blueprint, request, jsonify
import pandas as pd
import joblib
from tensorflow.keras.models import load_model
import os

pred_bp = Blueprint("prediction", __name__)

# Load model dan scaler
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models/saved_models")

# Load saved models
model = load_model(os.path.join(MODEL_DIR, "baby_nutrition_model.h5"))
scaler_X = joblib.load(os.path.join(MODEL_DIR, "scaler_X.save"))
scaler_y = joblib.load(os.path.join(MODEL_DIR, "scaler_y.save"))


def encode_input(usia_bulan, gender, berat_kg, tinggi_cm, aktivitas_level, status_asi):
    """
    Mengubah input kategorikal menjadi nilai numerik.

    Parameters:
        usia_bulan (int): Usia bayi dalam bulan
        gender (str): Jenis kelamin ('L' atau 'P')
        berat_kg (float): Berat badan dalam kg
        tinggi_cm (float): Tinggi badan dalam cm
        aktivitas_level (str): Level aktivitas ('Rendah', 'Sedang', 'Aktif', 'Sangat_Aktif')
        status_asi (str): Status ASI ('ASI_Eksklusif', 'ASI+MPASI', 'MPASI')

    Returns:
        dict: Data yang sudah diencode

    Raises:
        ValueError: Jika input tidak valid
    """
    # Mapping kategori ke nilai encoding
    gender_mapping = {"L": 0, "P": 1}
    aktivitas_mapping = {"Rendah": 1, "Sedang": 3, "Aktif": 0, "Sangat_Aktif": 2}
    status_asi_mapping = {"ASI_Eksklusif": 1, "ASI+MPASI": 0, "MPASI": 2}

    # Encode data input
    try:
        encoded_data = {
            "Usia_Bulan": usia_bulan,
            "Gender": gender_mapping[gender],
            "Berat_Kg": berat_kg,
            "Tinggi_Cm": tinggi_cm,
            "Aktivitas_Level": aktivitas_mapping[aktivitas_level],
            "Status_ASI": status_asi_mapping[status_asi],
        }
        return encoded_data
    except KeyError as e:
        raise ValueError(f"Invalid input for encoding: {e}")


def predict_nutrition(params):
    """
    Memprediksi kebutuhan nutrisi berdasarkan parameter input.

    Parameters:
        params (dict): Dictionary berisi parameter prediksi
            {
                "age": int,
                "weight": float,
                "gender": str,
                "height": float,
                "activity": str,
                "asi_status": str
            }

    Returns:
        dict: Hasil prediksi kebutuhan nutrisi
            {
                "calories": float,
                "proteins": float,
                "fat": float,
                "carbohydrate": float
            }

    Raises:
        ValueError: Jika parameter tidak valid
    """
    try:
        # Encode input
        encoded_input = encode_input(
            usia_bulan=params["age"],
            gender=params["gender"],
            berat_kg=params["weight"],
            tinggi_cm=params["height"],
            aktivitas_level=params["activity"],
            status_asi=params["asi_status"],
        )

        # Konversi ke DataFrame
        input_df = pd.DataFrame([encoded_input])

        # Normalisasi input
        input_scaled = scaler_X.transform(input_df)

        # Prediksi
        pred_scaled = model.predict(input_scaled)

        # Balikkan normalisasi pada prediksi
        prediction = scaler_y.inverse_transform(pred_scaled)

        return {
            "calories_needed": float(max(0, prediction[0][0])),
            "proteins_needed": float(max(0, prediction[0][1])),
            "fat_needed": float(max(0, prediction[0][2])),
            "carbohydrate_needed": float(max(0, prediction[0][3])),
        }
    except Exception as e:
        raise ValueError(f"Prediction error: {str(e)}")


# 127.0.0.1:5000/api/prediction/predict_nutrition
@pred_bp.route("/predict_nutrition", methods=["POST"])
def get_nutrition_prediction():
    """
    API endpoint untuk prediksi kebutuhan nutrisi.

    Request Body:
    {
        "usia_bulan": int,
        "gender": str,
        "berat_kg": float,
        "tinggi_cm": float,
        "aktivitas_level": str,
        "status_asi": str
    }

    Returns:
        JSON response dengan hasil prediksi atau pesan error
    """
    try:
        data = request.get_json()

        # Validasi field
        required_fields = [
            "usia_bulan",
            "gender",
            "berat_kg",
            "tinggi_cm",
            "aktivitas_level",
            "status_asi",
        ]
        for field in required_fields:
            if field not in data:
                return (
                    jsonify({"status": "error", "message": f"Missing field: {field}"}),
                    400,
                )

        # Format parameter untuk prediksi
        prediction_params = {
            "age": data["usia_bulan"],
            "weight": data["berat_kg"],
            "gender": data["gender"],
            "height": data["tinggi_cm"],
            "activity": data["aktivitas_level"],
            "asi_status": data["status_asi"],
        }

        # Prediksi
        prediction = predict_nutrition(prediction_params)

        return jsonify({"status": "success", "data": prediction}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
