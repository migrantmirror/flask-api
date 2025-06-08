from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "Welcome to the Flask API. Use the /api/odds endpoint."

@app.route("/api/odds")
def get_odds():
    return jsonify({"message": "Odds endpoint works!"})

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "This route does not exist. Try / or /api/odds"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
