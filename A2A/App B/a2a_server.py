from flask import Flask, request, jsonify
from code_gen import generate_code_from_json  # Reuse your function

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    api_key = data.get("api_key")
    file_json = data.get("json_data")
    
    if not api_key or not file_json:
        return jsonify({"error": "Missing API key or json data"}), 400

    result = generate_code_from_json(api_key, file_json)
    return jsonify(result)

if __name__ == "__main__":
    app.run(port=8001)
