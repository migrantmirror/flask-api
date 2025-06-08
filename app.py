from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import traceback

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Welcome to the Flask API. Use the /api/odds endpoint."

@app.route('/api/odds')
def get_odds():
    url = "https://api.football-data.org/v4/matches"
    headers = {
        "X-Auth-Token": "a99f297052584b1f85b4a62734cbd330"
    }

    params = {
        "dateFrom": datetime.today().strftime('%Y-%m-%d'),
        "dateTo": datetime.today().strftime('%Y-%m-%d')
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        predictions = []
        for match in data.get("matches", []):
            predictions.append({
                "match_id": match.get("id"),
                "competition": match.get("competition", {}).get("name"),
                "utc_date": match.get("utcDate"),
                "home_team": match.get("homeTeam", {}).get("name"),
                "away_team": match.get("awayTeam", {}).get("name"),
                "status": match.get("status"),
                "score": match.get("score", {}),
            })

        return jsonify(predictions)

    except Exception as e:
        traceback.print_exc()  # Logs full error in terminal
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "This route does not exist. Try / or /api/odds"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
