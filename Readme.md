# Flask PostGIS Example (schools)

This project serves a GeoJSON of schools. Changes made:

- Added PostGIS-backed storage using SQLAlchemy + GeoAlchemy2.
- Added `load_data.py` to push `data/sec.geojson` into the PostGIS `schools` table.
- `main.py` now reads features from the database and provides spatial endpoints: bbox, nearest, and stats.

Database connection is configured in `db.py`:

postgresql://postgres:password_0323@localhost:5432/schools_ke

Setup steps (local dev):

1. Create the database and enable PostGIS (requires superuser permissions):

   - Create DB:
     - In psql: `CREATE DATABASE schools_ke;`
   - Enable PostGIS (if your user has privileges):
     - `\c schools_ke` then `CREATE EXTENSION postgis;`

2. Install Python deps (prefer a virtualenv):

   pip install -r requirements.txt

3. Load the GeoJSON into the database:

   python load_data.py

   The loader will attempt to `CREATE EXTENSION IF NOT EXISTS postgis;` and then insert features from `data/sec.geojson`.

4. Run the Flask app:

   python main.py

Endpoints:

- GET /schools -> returns all features
- GET /schools?bbox=minx,miny,maxx,maxy -> features intersecting bbox
- GET /schools?lon=<lon>&lat=<lat>&k=5 -> nearest k features to point
- GET /schools/stats -> count and extent of stored geometries

Notes:

- If you cannot create the PostGIS extension from the script (permissions), create it manually as shown above.
- The loader maps `properties` to a JSON column and attempts to use common `name` properties.
# Flask Simple WebGIS Showing Schools

## Overview

This project is a simple WebGIS (Web-based Geographic Information System) application built using Flask. It visualizes school locations on an interactive web map, enabling users to explore spatial data in an intuitive way.

## Features

- Displays school locations on an interactive web map.
- Uses Flask as the backend framework.
- Integrates Leaflet.js for map rendering.
- Supports searching and filtering school data.
- Lightweight and easy to deploy.

## Technologies Used

- Flask (Python web framework)
- Leaflet.js (JavaScript library for interactive maps)
- HTML, CSS, JavaScript (Frontend UI)
- GeoJSON (Data format for storing school locations)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ClementNdome/flask-app-deploy.git
   cd flask-app-deploy
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python main.py
   ```
5. Open a web browser and go to `http://localhost:5000`.

## Usage

- Navigate the interactive map.
- Click on school markers for more details.
- Use search functionality to find specific schools.

## Deployment

This application is deployed and can be accessed anytime at:
👉 [Live WebGIS App](https://webgis-schools.onrender.com)

### Alternative Deployment Options
If you wish to deploy on other platforms, consider:
- Docker for containerized deployment.
- AWS or Google Cloud for scalable hosting.
- Nginx and uWSGI for advanced production setups.

## License

This project is licensed under the MIT License.

## Author

[Clement Ndome](https://github.com/ClementNdome)

