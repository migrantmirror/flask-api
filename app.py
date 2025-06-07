from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

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
            fixture_date = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00")).date()

            if fixture_date == today:
                bets = item.get("bets", [])
                correct_score = None
                over_under = None
                match_winner_odds = None

                for bet in bets:
                    if bet["label_name"] == "Correct Score":
                        correct_score = bet["values"][:3]
                    elif bet["label_name"] == "Over/Under":
                        over_under = bet["values"][:2]
                    elif bet["label_name"] == "Match Winner":
                        match_winner_odds = bet["values"]

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
