

from flask import Flask, jsonify, render_template
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE_URL = "postgresql://postgres:0323@localhost:5432/schools_db" # 0323 replace with your postgres password 
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schools')
def get_schools():
    query = session.execute(
        text("SELECT gid, name, ST_AsGeoJSON(geom) as geom FROM secondary_schools")
    )
    schools = [{"gid": row.gid, "name": row.name, "geometry": row.geom} for row in query]
    return jsonify(schools)

if __name__ == '__main__':
    app.run()
