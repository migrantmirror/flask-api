from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import traceback
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def home():
    return "Welcome to the Flask API. Use the /api/odds endpoint with query parameters."

@app.route('/api/odds')
def get_odds():
    url = "https://api.football-data.org/v4/matches"
    headers = {
        "X-Auth-Token": "a99f297052584b1f85b4a62734cbd330"  # Your valid token
    }

    date_from = request.args.get('dateFrom', datetime.today().strftime('%Y-%m-%d'))
    date_to = request.args.get('dateTo', datetime.today().strftime('%Y-%m-%d'))
    competition = request.args.get('competition')

    params = {
        "dateFrom": date_from,
        "dateTo": date_to
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches", [])

        if competition:
            matches = [m for m in matches if m.get("competition", {}).get("code") == competition]

        predictions = []
        for match in matches:
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
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ✅ Production-safe run block
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
