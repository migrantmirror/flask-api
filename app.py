import os
import math
import threading
import traceback
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Secure API Keys from environment
FOOTBALL_API_TOKEN = os.getenv("FOOTBALL_API_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

API_BASE = "https://api.football-data.org/v4"
ODDS_BASE = "https://api.the-odds-api.com/v4"
WEATHER_BASE = "https://api.openweathermap.org/data/2.5/weather"

HEADERS = {"X-Auth-Token": FOOTBALL_API_TOKEN}

# Caching
class CacheItem:
    def __init__(self, data, expires_at):
        self.data = data
        self.expires_at = expires_at

def ttl_cache(ttl):
    store, lock = {}, threading.Lock()
    def decorator(fn):
        def wrapper(*args):
            key = (fn.__name__,) + args
            with lock:
                item = store.get(key)
                if item and item.expires_at > datetime.utcnow():
                    return item.data
            result = fn(*args)
            with lock:
                store[key] = CacheItem(result, datetime.utcnow() + timedelta(seconds=ttl))
            return result
        return wrapper
    return decorator

# Standings endpoint
@app.route('/api/standings')
@ttl_cache(1800)
def standings():
    league = request.args.get("league")
    if not league:
        return jsonify({"error": "league param is required"}), 400
    r = requests.get(f"{API_BASE}/competitions/{league}/standings", headers=HEADERS)
    r.raise_for_status()
    return jsonify(r.json())

# Lineups endpoint
@app.route('/api/lineups')
@ttl_cache(900)
def lineups():
    match_id = request.args.get("match_id")
    if not match_id:
        return jsonify({"error": "match_id is required"}), 400
    r = requests.get(f"{API_BASE}/matches/{match_id}/lineups", headers=HEADERS)
    r.raise_for_status()
    return jsonify(r.json())

# Odds detail endpoint
@app.route('/api/odds_detail')
@ttl_cache(300)
def odds_detail():
    match_id = request.args.get("match_id")
    if not match_id:
        return jsonify({"error": "match_id is required"}), 400
    r = requests.get(
        f"{ODDS_BASE}/sports/soccer/odds",
        params={"apiKey": ODDS_API_KEY, "regions": "uk", "markets": "h2h,totals", "matchId": match_id}
    )
    r.raise_for_status()
    return jsonify(r.json())

# Historical results
@app.route('/api/history')
@ttl_cache(3600)
def history():
    team_id = request.args.get("team_id")
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400
    four_months_ago = datetime.utcnow() - timedelta(days=120)
    r = requests.get(
        f"{API_BASE}/teams/{team_id}/matches",
        headers=HEADERS,
        params={"dateFrom": four_months_ago.strftime("%Y-%m-%d"), "status": "FINISHED"}
    )
    r.raise_for_status()
    return jsonify(r.json())

# Weather endpoint
@app.route('/api/weather')
def weather():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "city is required"}), 400
    r = requests.get(WEATHER_BASE, params={"q": city, "appid": WEATHER_API_KEY, "units": "metric"})
    r.raise_for_status()
    d = r.json()
    return jsonify({"temp": d["main"]["temp"], "weather": d["weather"][0]["description"]})

# Poisson and Kelly

def poisson(lmbda, k):
    return (lmbda ** k) * math.exp(-lmbda) / math.factorial(k)

def implied_prob(o):
    return 1 / o if o else 0

def kelly_fraction(p, b):
    q = 1 - p
    return max(0, (b * p - q) / b)

@app.route('/api/predict')
def predict():
    try:
        home_avg = float(request.args.get("home_avg", 1.5))
        away_avg = float(request.args.get("away_avg", 1.2))
        home_odds = float(request.args.get("home_odds", 2.1))
        draw_odds = float(request.args.get("draw_odds", 3.3))
        away_odds = float(request.args.get("away_odds", 3.1))

        matrix = [[poisson(home_avg, i) * poisson(away_avg, j) for j in range(6)] for i in range(6)]

        home_win_prob = sum(matrix[i][j] for i in range(6) for j in range(6) if i > j)
        draw_prob = sum(matrix[i][i] for i in range(6))
        away_win_prob = sum(matrix[i][j] for i in range(6) for j in range(6) if i < j)

        imp_home, imp_draw, imp_away = map(implied_prob, [home_odds, draw_odds, away_odds])

        value_bets = [side for side, mp, ip in [
            ("home", home_win_prob, imp_home),
            ("draw", draw_prob, imp_draw),
            ("away", away_win_prob, imp_away)
        ] if mp > ip + 0.05]

        stakes = {side: round(kelly_fraction(mp, odds), 3) for side, mp, odds in [
            ("home", home_win_prob, home_odds),
            ("draw", draw_prob, draw_odds),
            ("away", away_win_prob, away_odds)
        ]}

        return jsonify({
            "prob_home": round(home_win_prob, 3),
            "prob_draw": round(draw_prob, 3),
            "prob_away": round(away_win_prob, 3),
            "value_bets": value_bets,
            "suggested_stakes": stakes
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
