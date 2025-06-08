from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Welcome to the Flask API. Use the /api/odds endpoint."

@app.route('/api/odds')
def get_odds():
    url = "https://football-pro.p.rapidapi.com/api/v2.0/corrections/season/17141?tz=Europe%2FAmsterdam"
    headers = {
        "x-rapidapi-host": "football-pro.p.rapidapi.com",
        "x-rapidapi-key": "4c92911f15msh5e8dba7681d7212p141557jsnbce9e8b77d8e"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        raw_data = response.json()

        today = datetime.now(timezone.utc).date()
        filtered_matches = []

        corrections = raw_data.get("data", [])
        for correction in corrections:
            fixture = correction.get("fixture")
            if not fixture:
                continue

            fixture_date_str = fixture.get("starting_at", {}).get("date")
            if not fixture_date_str:
                continue

            try:
                fixture_date = datetime.fromisoformat(fixture_date_str).date()
            except Exception:
                continue

            if fixture_date == today:
                filtered_matches.append({
                    "fixture_id": fixture.get("id"),
                    "teams": {
                        "home": fixture.get("participants", [{}])[0].get("name"),
                        "away": fixture.get("participants", [{}])[1].get("name") if len(fixture.get("participants", [])) > 1 else None
                    },
                    "start_time": fixture.get("starting_at", {}).get("time"),
                    "venue": fixture.get("venue", {}).get("name")
                })

        return jsonify(filtered_matches)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "This route does not exist. Try / or /api/odds"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
