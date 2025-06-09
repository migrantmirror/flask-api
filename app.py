from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import math
import os
import threading
import traceback

app = Flask(__name__)
CORS(app)

API_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_API_TOKEN = os.environ.get("FOOTBALL_API_TOKEN", "a99f297052584b1f85b4a62734cbd330")

HEADERS = {"X-Auth-Token": FOOTBALL_API_TOKEN}

# Thread-safe cache for team stats with TTL
class CacheItem:
    def __init__(self, data, expires_at):
        self.data = data
        self.expires_at = expires_at

team_stats_cache = {}
cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 3600  # 1 hour cache

def get_cached_team_stats(team_id):
    with cache_lock:
        item = team_stats_cache.get(team_id)
        if item and item.expires_at > datetime.utcnow():
            return item.data
        return None

def set_cached_team_stats(team_id, data):
    with cache_lock:
        expires_at = datetime.utcnow() + timedelta(seconds=CACHE_TTL_SECONDS)
        team_stats_cache[team_id] = CacheItem(data, expires_at)

def poisson(lmbda, k):
    return (lmbda ** k) * math.exp(-lmbda) / math.factorial(k)

def fetch_team_matches(team_id, days=60):
    # Fetch finished matches for team within last `days`
    date_to = datetime.utcnow()
    date_from = date_to - timedelta(days=days)
    url = f"{API_BASE_URL}/teams/{team_id}/matches"
    params = {
        "dateFrom": date_from.strftime("%Y-%m-%d"),
        "dateTo": date_to.strftime("%Y-%m-%d"),
        "status": "FINISHED"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("matches", [])

def calculate_attack_defense(team_id):
    cached = get_cached_team_stats(team_id)
    if cached:
        return cached

    matches = fetch_team_matches(team_id)
    if not matches:
        return None, None

    goals_for = 0
    goals_against = 0
    for m in matches:
        if m["homeTeam"]["id"] == team_id:
            goals_for += m["score"]["fullTime"]["home"]
            goals_against += m["score"]["fullTime"]["away"]
        else:
            goals_for += m["score"]["fullTime"]["away"]
            goals_against += m["score"]["fullTime"]["home"]

    attack = goals_for / len(matches)
    defense = goals_against / len(matches)
    set_cached_team_stats(team_id, (attack, defense))
    return attack, defense

def expected_goals_dynamic(home_attack, away_defense, avg_home_goals,
                           away_attack, home_defense, avg_away_goals):
    exp_home = home_attack * away_defense * avg_home_goals
    exp_away = away_attack * home_defense * avg_away_goals
    return exp_home, exp_away

# Caching for live matches
live_matches_cache = CacheItem(data=None, expires_at=datetime.utcnow())
live_matches_lock = threading.Lock()
LIVE_MATCHES_CACHE_TTL = 300  # 5 minutes cache

@app.route('/')
def home():
    return "Welcome to the Flask API. Use /api/predict with params: home_team_id, away_team_id, home_odds, draw_odds, away_odds."

@app.route('/api/predict')
def predict():
    try:
        home_team_id = request.args.get("home_team_id", type=int)
        away_team_id = request.args.get("away_team_id", type=int)
        home_odds = request.args.get("home_odds", type=float)
        draw_odds = request.args.get("draw_odds", type=float)
        away_odds = request.args.get("away_odds", type=float)

        if not all([home_team_id, away_team_id, home_odds, draw_odds, away_odds]):
            return jsonify({"error": "Missing required parameters: home_team_id, away_team_id, home_odds, draw_odds, away_odds"}), 400

        home_attack, home_defense = calculate_attack_defense(home_team_id)
        away_attack, away_defense = calculate_attack_defense(away_team_id)

        if None in [home_attack, home_defense, away_attack, away_defense]:
            return jsonify({"error": "Not enough data to calculate team stats"}), 400

        # For now, average league goals estimated from team stats (improvable with league-wide data)
        avg_home_goals = (home_attack + away_defense) / 2
        avg_away_goals = (away_attack + home_defense) / 2

        exp_home, exp_away = expected_goals_dynamic(
            home_attack, away_defense, avg_home_goals,
            away_attack, home_defense, avg_away_goals
        )

        max_goals = 5
        home_probs = [poisson(exp_home, i) for i in range(max_goals + 1)]
        away_probs = [poisson(exp_away, i) for i in range(max_goals + 1)]

        home_win_prob = 0
        draw_prob = 0
        away_win_prob = 0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = home_probs[i] * away_probs[j]
                if i > j:
                    home_win_prob += p
                elif i == j:
                    draw_prob += p
                else:
                    away_win_prob += p

        def implied_prob(odds):
            try:
                return 1 / odds
            except Exception:
                return None

        imp_home = implied_prob(home_odds)
        imp_draw = implied_prob(draw_odds)
        imp_away = implied_prob(away_odds)

        margin = 0.05
        value_bets = []
        if imp_home and home_win_prob > imp_home + margin:
            value_bets.append("home_win")
        if imp_draw and draw_prob > imp_draw + margin:
            value_bets.append("draw")
        if imp_away and away_win_prob > imp_away + margin:
            value_bets.append("away_win")

        result = {
            "teams": {"home_team_id": home_team_id, "away_team_id": away_team_id},
            "expected_goals": {"home": round(exp_home, 2), "away": round(exp_away, 2)},
            "outcome_probabilities": {
                "home_win": round(home_win_prob, 3),
                "draw": round(draw_prob, 3),
                "away_win": round(away_win_prob, 3),
            },
            "bookmaker_odds": {"home": home_odds, "draw": draw_odds, "away": away_odds},
            "implied_probabilities": {
                "home": round(imp_home, 3) if imp_home else None,
                "draw": round(imp_draw, 3) if imp_draw else None,
                "away": round(imp_away, 3) if imp_away else None,
            },
            "value_bets": value_bets,
        }

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/live-matches')
def live_matches():
    try:
        date_from = request.args.get("dateFrom", datetime.utcnow().strftime("%Y-%m-%d"))
        date_to = request.args.get("dateTo", datetime.utcnow().strftime("%Y-%m-%d"))

        with live_matches_lock:
            # Check cache expiry
            if live_matches_cache.data and live_matches_cache.expires_at > datetime.utcnow():
                return jsonify(live_matches_cache.data)

            # Fetch live/upcoming matches from external API
            url = f"{API_BASE_URL}/matches"
            params = {
                "dateFrom": date_from,
                "dateTo": date_to,
                # You can add more filters if needed
            }
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()

            matches = data.get("matches", [])

            # Simplify matches data to only essential info
            simplified_matches = []
            for m in matches:
                simplified_matches.append({
                    "match_id": m.get("id"),
                    "utc_date": m.get("utcDate"),
                    "status": m.get("status"),
                    "home_team": m.get("homeTeam", {}).get("name"),
                    "away_team": m.get("awayTeam", {}).get("name"),
                    "score": m.get("score"),
                })

            # Cache the data
            live_matches_cache.data = simplified_matches
            live_matches_cache.expires_at = datetime.utcnow() + timedelta(seconds=LIVE_MATCHES_CACHE_TTL)

            return jsonify(simplified_matches)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
