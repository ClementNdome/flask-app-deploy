from flask import Flask, jsonify, render_template
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schools')
def get_schools():
    # Load local GeoJSON file
    with open("data/sec.geojson") as f:
        schools_data = json.load(f)
    return jsonify(schools_data)

if __name__ == '__main__':
    app.run()
