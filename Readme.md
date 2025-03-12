# Flask Simple WebGIS Showing Schools

## Overview
This project is a simple WebGIS (Web-based Geographic Information System) application built using Flask. It visualizes school locations on an interactive web map, enabling users to explore spatial data in an intuitive way.

## Features
- Displays school locations on an interactive web map.
- Uses Flask as the backend framework.
- Integrates Leaflet.js for map rendering.
- Supports searching and filtering school data.
- Lightweight and easy to deploy.
- Responsive design for mobile and desktop usage.

## Technologies Used
- Flask (Python web framework)
- Leaflet.js (JavaScript library for interactive maps)
- HTML, CSS, JavaScript (Frontend UI)
- GeoJSON (Data format for storing school locations)
- SQLite/PostgreSQL (Database support for storing location data)

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/ClementNdome/flask-simple-webgis-showing-schools.git
   cd flask-simple-webgis-showing-schools
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
   python app.py
   ```
5. Open a web browser and go to `http://localhost:5000`.

## Usage
- Navigate the interactive map.
- Click on school markers for more details.
- Use search functionality to find specific schools.
- Filter schools based on attributes such as location type or region.

## Deployment
This application can be deployed using:
- Flask’s built-in development server (not recommended for production)
- Gunicorn or uWSGI for production
- Hosting services like Heroku, Render, or DigitalOcean

## Future Improvements
- Implement user authentication for managing school data.
- Add more spatial analysis functionalities.
- Integrate additional map layers for enhanced visualization.

## License
This project is licensed under the MIT License.

## Author
[Clement Ndome](https://github.com/ClementNdome)

