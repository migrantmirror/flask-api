from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    # Root route to avoid 404 errors for "/"
    return "Welcome to the Flask API. Use the /api/odds endpoint."

@app.route('/api/odds')
def get_odds():
    url = "https://api-football-v1.p.rapidapi.com/v2/odds/league/865927/bookmaker/5?page=2"
    headers = {
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
        "x-rapidapi-key": "04bbd874ddmshbc1a243b2925c63p16b9fdjsn3acacc503dd8"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        raw_data = response.json()

        today = datetime.now(timezone.utc).date()
        filtered_predictions = []

        for item in raw_data.get("api", {}).get("odds", []):
            fixture = item.get("fixture", {})
            fixture_date_str = fixture.get("event_date") or fixture.get("fixture_date")
            if not fixture_date_str:
                continue  # skip if date is missing

            try:
                fixture_date = datetime.fromisoformat(
                    fixture_date_str.replace("Z", "+00:00")
                ).date()
            except Exception:
                continue  # skip if date is malformed

            if fixture_date == today:
                bets = item.get("bets", [])
                correct_score = None
                over_under = None
                match_winner_odds = None

                for bet in bets:
                    if bet.get("label_name") == "Correct Score":
                        correct_score = bet.get("values", [])[:3]
                    elif bet.get("label_name") == "Over/Under":
                        over_under = bet.get("values", [])[:2]
                    elif bet.get("label_name") == "Match Winner":
                        match_winner_odds = bet.get("values", [])

                filtered_predictions.append({
                    "fixture_id": fixture.get("fixture_id"),
                    "teams": {
                        "home": fixture.get("homeTeam", {}).get("team_name"),
                        "away": fixture.get("awayTeam", {}).get("team_name")
                    },
                    "correct_score": correct_score,
                    "over_under": over_under,
                    "match_winner_odds": match_winner_odds
                })

        return jsonify(filtered_predictions)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    # Custom handler for all other undefined routes
    return jsonify({"error": "This route does not exist. Try / or /api/odds"}), 404

if __name__ == '__main__':
    # Use 0.0.0.0 for accessibility on local network
    app.run(host='0.0.0.0', port=5000)
