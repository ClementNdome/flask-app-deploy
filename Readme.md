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

