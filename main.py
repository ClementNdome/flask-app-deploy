from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import json

from db import get_session
from models import School, Staff, Facility, Incident, Program
from sqlalchemy import select, func, text
from services.analytics import EducationAnalytics

import requests
from shapely.geometry import shape as shapely_shape
from geoalchemy2 import WKTElement
import os
import threading
from datetime import datetime, timedelta
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from services.auth import AuthService
from models import User
import io
import pandas as pd
from flask import send_file
from services.cache import make_cache_decorator

# Simple Nominatim cache persisted to disk to reduce external calls
CACHE_FILE = "nominatim_cache.json"
nominatim_cache = {}
cache_lock = threading.Lock()


def load_cache():
    global nominatim_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                nominatim_cache = json.load(f)
        else:
            nominatim_cache = {}
    except Exception:
        nominatim_cache = {}


def save_cache():
    try:
        with cache_lock:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(nominatim_cache, f)
    except Exception:
        pass


# load cache at startup
load_cache()

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('APP_SECRET', 'dev-secret')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    session = get_session()
    try:
        return session.query(User).get(int(user_id))
    finally:
        session.close()


@app.route('/schools/knn')
def schools_knn():
    """Fast nearest neighbors using PostGIS KNN (<->) operator and GiST index.
    Query params: lon, lat, k
    """
    lon = request.args.get('lon')
    lat = request.args.get('lat')
    try:
        k = int(request.args.get('k', 5))
    except Exception:
        k = 5

    if not lon or not lat:
        return jsonify({'error': 'Provide lon and lat'}), 400

    try:
        lon_f = float(lon); lat_f = float(lat)
    except Exception:
        return jsonify({'error': 'Invalid coordinates'}), 400

    sql = text(
        "SELECT id, name, properties, ST_AsGeoJSON(geom)::json AS geojson, "
        "ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m "
        "FROM schools "
        "ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
        "LIMIT :k"
    )
    session = get_session()
    try:
        rows = session.execute(sql.bindparams(lon=lon_f, lat=lat_f, k=k)).mappings().all()
        features = []
        for r in rows:
            props = r.get('properties') or {}
            if r.get('name') and not props.get('name'):
                props['name'] = r.get('name')
            props['distance_m'] = float(r.get('distance_m') or 0)
            features.append({ 'type':'Feature', 'properties': props, 'geometry': r.get('geojson'), 'id': r.get('id') })
        return jsonify({ 'type':'FeatureCollection', 'features': features })
    finally:
        session.close()


@app.route('/schools/heatgrid')
def schools_heatgrid():
    """Return aggregated grid cells (in meters) with counts for heatmap visualization.
    Params: grid_size (meters, default=1000), bbox (minx,miny,maxx,maxy optional)
    """
    try:
        grid_size = float(request.args.get('grid_size', 1000))
    except Exception:
        grid_size = 1000.0

    bbox = request.args.get('bbox')
    session = get_session()
    try:
        params = {'size': grid_size}
        bbox_filter = ''
        if bbox:
            try:
                minx, miny, maxx, maxy = [float(x) for x in bbox.split(',')]
                # transform bbox to 3857 to compare in meters
                bbox_filter = "WHERE ST_Intersects(geom, ST_Transform(ST_MakeEnvelope(:minx,:miny,:maxx,:maxy,4326),3857))"
                params.update({'minx': minx, 'miny': miny, 'maxx': maxx, 'maxy': maxy})
            except Exception:
                return jsonify({'error':'Invalid bbox'}), 400

        # Snap to 3857 grid, aggregate counts, then return geometries back in 4326
        sql = text(f"""
            SELECT ST_AsGeoJSON(ST_Transform(ST_SnapToGrid(ST_Transform(geom,3857), :size, :size), 4326))::json AS geom, COUNT(*) as cnt
            FROM schools
            {bbox_filter}
            GROUP BY 1
            ORDER BY cnt DESC
            LIMIT 1000
        """
        )
        rows = session.execute(sql, params).mappings().all()
        features = []
        for r in rows:
            if r.get('geom') is None:
                continue
            features.append({'type':'Feature', 'properties': {'count': int(r.get('cnt') or 0)}, 'geometry': r.get('geom')})
        return jsonify({'type':'FeatureCollection', 'features': features})
    finally:
        session.close()


@app.route('/schools/cluster')
@make_cache_decorator(ttl=30)
def schools_cluster():
    """Return simple k-means clusters computed in Python from school centroids.
    Params: k (clusters, default 10)
    This is a fallback clustering endpoint for quick visual grouping.
    """
    try:
        k = int(request.args.get('k', 10))
    except Exception:
        k = 10

    session = get_session()
    try:
        rows = session.execute(text("SELECT id, ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat FROM schools")).mappings().all()
        points = [(float(r['lat']), float(r['lon']), int(r['id'])) for r in rows if r['lon'] is not None and r['lat'] is not None]
        if not points:
            return jsonify({'type':'FeatureCollection', 'features': []})

        # simple kmeans via scikit-like implementation without dependency
        # initialize centroids by sampling
        import random
        centroids = [ (random.choice(points)[0], random.choice(points)[1]) for _ in range(min(k, len(points))) ]

        def assign(p, cents):
            best = 0; bestd = None
            for i,c in enumerate(cents):
                d = (p[0]-c[0])**2 + (p[1]-c[1])**2
                if bestd is None or d < bestd:
                    bestd = d; best = i
            return best

        for _ in range(10):
            clusters = {i: [] for i in range(len(centroids))}
            for p in points:
                idx = assign(p, centroids)
                clusters[idx].append(p)
            newc = []
            for i in range(len(centroids)):
                pts = clusters[i]
                if pts:
                    avg_lat = sum([pt[0] for pt in pts])/len(pts)
                    avg_lon = sum([pt[1] for pt in pts])/len(pts)
                    newc.append((avg_lat, avg_lon))
                else:
                    newc.append(centroids[i])
            centroids = newc

        # produce GeoJSON points for centroids with size
        features = []
        for i,c in enumerate(centroids):
            count = len(clusters.get(i, []))
            features.append({'type':'Feature', 'properties':{'cluster': i, 'count': count}, 'geometry': {'type':'Point','coordinates':[c[1], c[0]]}})

        return jsonify({'type':'FeatureCollection', 'features': features})
    finally:
        session.close()


@app.route('/')
def index():
    # pass map center and zoom as template variables
    center = [-1.286389, 36.817223]
    zoom = 7
    # detect if local vendored leaflet.draw exists and load integrity info if present
    static_vendor_path = os.path.join(app.static_folder or 'static', 'vendor', 'leaflet-draw')
    use_local_leaflet_draw = os.path.exists(os.path.join(static_vendor_path, 'leaflet.draw.js'))
    leaflet_draw_integrity = {}
    try:
        integ_path = os.path.join(static_vendor_path, 'integrity.json')
        if os.path.exists(integ_path):
            with open(integ_path, 'r', encoding='utf-8') as f:
                leaflet_draw_integrity = json.load(f)
    except Exception:
        leaflet_draw_integrity = {}

    return render_template('index.html', center=center, zoom=zoom, use_local_leaflet_draw=use_local_leaflet_draw, leaflet_draw_integrity=leaflet_draw_integrity)


@app.route('/nearest')
def page_nearest():
    center = [-1.286389, 36.817223]
    zoom = 7
    return render_template('nearest.html', center=center, zoom=zoom)


@app.route('/buffer')
def page_buffer():
    center = [-1.286389, 36.817223]
    zoom = 7
    return render_template('buffer.html', center=center, zoom=zoom)


@app.route('/map-stats')
def page_stats():
    center = [-1.286389, 36.817223]
    zoom = 7
    return render_template('stats.html', center=center, zoom=zoom)


def row_to_feature(row):
    # row: (id, name, properties, geojson)
    geom_json = row.geojson
    geometry = None
    if geom_json:
        try:
            geometry = json.loads(geom_json)
        except Exception:
            geometry = None

    props = row.properties or {}
    # ensure name present
    if row.name and not props.get('name'):
        props['name'] = row.name

    return {
        "type": "Feature",
        "properties": props,
        "geometry": geometry,
        "id": row.id,
    }


@app.route('/schools')
def get_schools():
    """Return GeoJSON FeatureCollection from the PostGIS `schools` table.

    Query parameters (optional):
      bbox=minx,miny,maxx,maxy   -- returns features intersecting this bbox
      lon & lat & k              -- returns nearest k features to this point
    """
    session = get_session()
    try:
        # Nearest search if lat/lon provided
        lon = request.args.get('lon')
        lat = request.args.get('lat')
        k = int(request.args.get('k') or 5)

        bbox = request.args.get('bbox')

        geo_col = School.__table__.c.geom

        if lon and lat:
            # nearest by great-circle distance (meters) using geography
            try:
                lon_f = float(lon)
                lat_f = float(lat)
            except ValueError:
                return jsonify({"error": "Invalid lat/lon"}), 400

            sql = text(
                "SELECT id, name, properties, ST_AsGeoJSON(geom) AS geojson, "
                "ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m "
                "FROM schools "
                "ORDER BY distance_m "
                "LIMIT :k"
            )

            rows = session.execute(sql.bindparams(lon=lon_f, lat=lat_f, k=k)).all()

        elif bbox:
            # bbox: minx,miny,maxx,maxy
            try:
                minx, miny, maxx, maxy = [float(x) for x in bbox.split(',')]
            except Exception:
                return jsonify({"error": "Invalid bbox format. Use minx,miny,maxx,maxy"}), 400

            envelope = func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)
            stmt = select(
                School.id,
                School.name,
                School.properties,
                func.ST_AsGeoJSON(School.geom).label('geojson'),
            ).where(func.ST_Intersects(School.geom, envelope))

            rows = session.execute(stmt).all()

        else:
            # return all
            stmt = select(
                School.id,
                School.name,
                School.properties,
                func.ST_AsGeoJSON(School.geom).label('geojson'),
            )
            rows = session.execute(stmt).all()

        features = []
        for r in rows:
            f = row_to_feature(r)
            # attach distance if present (nearest query)
            if hasattr(r, 'distance_m') and r.distance_m is not None:
                if 'properties' not in f or f['properties'] is None:
                    f['properties'] = {}
                f['properties']['distance_m'] = float(r.distance_m)
            features.append(f)

        return jsonify({"type": "FeatureCollection", "features": features})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route('/schools/stats')
def schools_stats():
    """Return simple spatial stats: count and extent."""
    session = get_session()
    try:
        count = session.execute(select(func.count()).select_from(School)).scalar_one()
        extent = session.execute(select(func.ST_Extent(School.geom))).scalar()
        return jsonify({"count": count, "extent": extent})
    finally:
        session.close()



@app.route('/schools/buffer')
def schools_buffer():
    """Return features within a radius (in km) of a point.

    Query params: lon, lat, radius_km, optional limit k
    """
    session = get_session()
    try:
        lon = request.args.get('lon')
        lat = request.args.get('lat')
        radius_km = request.args.get('radius_km')
        k = int(request.args.get('k') or 1000)

        if not lon or not lat or not radius_km:
            return jsonify({"error": "Provide lon, lat and radius_km"}), 400

        try:
            lon_f = float(lon)
            lat_f = float(lat)
            radius_m = float(radius_km) * 1000.0
        except ValueError:
            return jsonify({"error": "Invalid numeric parameters"}), 400

        # Use ST_DWithin with geography cast to calculate great-circle distances
        sql = text(
            "SELECT id, name, properties, ST_AsGeoJSON(geom) AS geojson"
            " FROM schools"
            " WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)"
            " LIMIT :k"
        )

        rows = session.execute(sql.bindparams(lon=lon_f, lat=lat_f, radius=radius_m, k=k)).all()

        # rows are Row objects with keys id,name,properties,geojson
        features = []
        for r in rows:
            geom_json = r.geojson
            geometry = None
            if geom_json:
                try:
                    geometry = json.loads(geom_json)
                except Exception:
                    geometry = None

            props = r.properties or {}
            if r.name and not props.get('name'):
                props['name'] = r.name

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geometry,
                "id": r.id,
            })

        return jsonify({"type": "FeatureCollection", "features": features})
    finally:
        session.close()


@app.route('/schools/within', methods=['POST'])
def schools_within():
    """Return features that intersect a posted GeoJSON geometry.

    Body: { "geometry": <GeoJSON geometry> }
    """
    data = request.get_json(silent=True)
    if not data or 'geometry' not in data:
        return jsonify({"error": "POST JSON with 'geometry' required"}), 400

    geom = data['geometry']
    geom_str = json.dumps(geom)

    session = get_session()
    try:
        sql = text(
            "SELECT id, name, properties, ST_AsGeoJSON(geom) AS geojson "
            "FROM schools "
            "WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))"
        )
        rows = session.execute(sql.bindparams(geom=geom_str)).all()

        features = []
        for r in rows:
            geom_json = r.geojson
            geometry = None
            if geom_json:
                try:
                    geometry = json.loads(geom_json)
                except Exception:
                    geometry = None

            props = r.properties or {}
            if r.name and not props.get('name'):
                props['name'] = r.name

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geometry,
                "id": r.id,
            })

        return jsonify({"type": "FeatureCollection", "features": features})
    finally:
        session.close()


@app.route('/schools/hull')
def schools_hull():
    """Return the convex hull polygon (GeoJSON) of all geometries in the table."""
    session = get_session()
    try:
        row = session.execute(text(
            "SELECT ST_AsGeoJSON(ST_ConvexHull(ST_Collect(geom))) as geojson FROM schools"
        )).first()
        if not row or not row.geojson:
            return jsonify({"type": "FeatureCollection", "features": []})

        geom = json.loads(row.geojson)
        feature = {"type": "Feature", "properties": {}, "geometry": geom}
        return jsonify({"type": "FeatureCollection", "features": [feature]})
    finally:
        session.close()


@app.route('/schools/stats/details')
def schools_stats_details():
    """Return counts grouped by administrative attribute (county/admin), if present."""
    session = get_session()
    try:
        sql = text(
            "SELECT COALESCE(properties->>'county', properties->>'COUNTY', properties->>'admin', properties->>'ADMIN', 'UNKNOWN') as key, "
            "count(*) as cnt FROM schools GROUP BY key ORDER BY cnt DESC"
        )
        rows = session.execute(sql).all()
        data = [{"key": r.key, "count": int(r.cnt)} for r in rows]
        return jsonify(data)
    finally:
        session.close()


@app.route('/schools/voronoi')
def schools_voronoi():
    """Generate Voronoi diagram showing school service areas.
    Optional params:
    - radius_km: buffer radius in km (default 10)
    Returns GeoJSON with voronoi polygons, buffer areas, and school points.
    """
    try:
        radius_km = float(request.args.get('radius_km', 10))
    except ValueError:
        return jsonify({"error": "Invalid radius"}), 400

    session = get_session()
    try:
        # First get the points
        points_sql = text("SELECT id, name, properties, ST_AsGeoJSON(geom)::json AS geojson FROM schools")
        points = session.execute(points_sql).mappings().all()
        point_features = []
        for p in points:
            props = p['properties'] or {}
            if p['name'] and not props.get('name'):
                props['name'] = p['name']
            point_features.append({
                "type": "Feature",
                "properties": props,
                "geometry": p['geojson'],
                "id": p['id']
            })

        # Generate Voronoi diagram
        voronoi_sql = text("""
            WITH
            bounds AS (
                SELECT ST_Envelope(ST_Collect(geom)) AS env,
                       ST_Buffer(ST_Envelope(ST_Collect(geom))::geography, :radius_m)::geometry AS buf_env
                FROM schools
            ),
            points AS (
                SELECT geom FROM schools
            ),
            voronoi AS (
                SELECT (ST_Dump(ST_VoronoiPolygons(ST_Collect(points.geom)))).geom AS cell
                FROM points, bounds
                WHERE ST_Intersects(bounds.env, points.geom)
            )
            SELECT ST_AsGeoJSON(ST_Intersection(
                cell,
                (SELECT buf_env FROM bounds)
            ))::json AS geojson
            FROM voronoi;
        """)
        voronoi_rows = session.execute(voronoi_sql, {"radius_m": radius_km * 1000}).mappings().all()
        voronoi_features = []
        for r in voronoi_rows:
            if r['geojson']:
                voronoi_features.append({
                    "type": "Feature",
                    "properties": {},
                    "geometry": r['geojson']
                })

        # Generate buffer
        buffer_sql = text("""
            SELECT ST_AsGeoJSON(
                ST_Buffer(
                    ST_Collect(geom)::geography,
                    :radius_m
                )::geometry
            )::json AS geojson
            FROM schools
        """)
        buffer = session.execute(buffer_sql, {"radius_m": radius_km * 1000}).scalar()

        return jsonify({
            "voronoi": {
                "type": "FeatureCollection",
                "features": voronoi_features
            },
            "buffer": {
                "type": "Feature",
                "properties": {},
                "geometry": buffer
            } if buffer else None,
            "points": {
                "type": "FeatureCollection",
                "features": point_features
            }
        })
    finally:
        session.close()


@app.route('/schools/analysis')
def page_analysis():
    """Render the enhanced education analytics dashboard page."""
    session = get_session()
    try:
        # Get initial statistics
        analytics = EducationAnalytics()
        stats = {
            "total_schools": session.query(func.count(School.id)).scalar() or 0,
            "total_enrollment": analytics.get_enrollment_statistics()['total_enrollment'],
            "avg_performance": analytics.get_performance_metrics()['average_performance_index'],
            "teacher_ratio": round(analytics.get_resource_distribution()['teacher_student_ratio'], 1)
        }
        
        # Get counties and school types for filters
        counties = session.query(School.county).distinct().all()
        counties = sorted([c[0] for c in counties if c[0]])
        
        school_types = session.query(School.school_type).distinct().all()
        school_types = sorted([t[0] for t in school_types if t[0]])
        
        center = [-1.286389, 36.817223]
        zoom = 7
        
        return render_template('analysis.html', 
                             center=center, 
                             zoom=zoom,
                             stats=stats,
                             counties=counties,
                             school_types=school_types)
    finally:
        session.close()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username')
    password = request.form.get('password')
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user and AuthService.verify_password(user, password):
            login_user(user)
            return json.dumps({'ok': True}), 200, {'ContentType': 'application/json'}
        return json.dumps({'ok': False, 'error': 'Invalid credentials'}), 401, {'ContentType': 'application/json'}
    finally:
        session.close()


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template('index.html', center=[-1.286389, 36.817223], zoom=7)


@app.route('/admin')
@login_required
def admin_panel():
    # basic admin view: list users (admin role required)
    if not current_user.role or current_user.role != 'admin':
        return "Forbidden", 403
    session = get_session()
    try:
        users = session.query(User).all()
        return render_template('admin.html', users=users)
    finally:
        session.close()


@app.route('/api/export/csv')
@login_required
def export_csv():
    # export current schools dataset or filtered view
    session = get_session()
    try:
        rows = session.query(
            School.id, School.name, School.county, School.school_type, School.current_enrollment, School.student_capacity
        ).all()
        df = pd.DataFrame([{
            'id': r.id, 'name': r.name, 'county': r.county, 'type': r.school_type,
            'enrollment': r.current_enrollment, 'capacity': r.student_capacity
        } for r in rows])
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(io.BytesIO(buf.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='schools.csv')
    finally:
        session.close()


@app.route('/api/export/excel')
@login_required
def export_excel():
    session = get_session()
    try:
        rows = session.query(
            School.id, School.name, School.county, School.school_type, School.current_enrollment, School.student_capacity
        ).all()
        df = pd.DataFrame([{
            'id': r.id, 'name': r.name, 'county': r.county, 'type': r.school_type,
            'enrollment': r.current_enrollment, 'capacity': r.student_capacity
        } for r in rows])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='schools')
        buf.seek(0)
        return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='schools.xlsx')
    finally:
        session.close()


@app.route('/api/export/pdf')
@login_required
def export_pdf():
    # create a simple PDF with a table of schools
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    session = get_session()
    try:
        rows = session.query(School.id, School.name, School.county, School.current_enrollment).all()
        data = [['ID', 'Name', 'County', 'Enrollment']] + [[r.id, r.name, r.county or '', r.current_enrollment or ''] for r in rows]
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN',(0,0),(-1,-1),'LEFT'),
            ('GRID',(0,0),(-1,-1),0.5,colors.black)
        ]))
        doc.build([table])
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='schools.pdf')
    finally:
        session.close()

@app.route('/api/dashboard/data')
def get_dashboard_data():
    """Provide data for the education analytics dashboard with optional filters."""
    county = request.args.get('county')
    school_type = request.args.get('school_type')
    metric = request.args.get('metric', 'performance')
    
    analytics = EducationAnalytics()
    
    # Get basic statistics
    enrollment_stats = analytics.get_enrollment_statistics(county)
    performance_stats = analytics.get_performance_metrics(school_type)
    resource_stats = analytics.get_resource_distribution()
    facility_stats = analytics.get_facility_status()
    incident_stats = analytics.get_incident_summary()
    staff_stats = analytics.get_staff_qualifications()
    coverage_stats = analytics.get_school_coverage_analysis()
    
    session = get_session()
    try:
        # Get schools for map visualization with filters
        query = session.query(
            School.id,
            School.name,
            School.school_type,
            School.current_enrollment,
            School.mean_score,
            func.ST_X(func.ST_Transform(School.geom, 4326)).label('lon'),
            func.ST_Y(func.ST_Transform(School.geom, 4326)).label('lat')
        )
        
        if county:
            query = query.filter(School.county == county)
        if school_type:
            query = query.filter(School.school_type == school_type)
            
        schools = [{
            'id': s.id,
            'name': s.name,
            'type': s.school_type,
            'enrollment': s.current_enrollment,
            'performance': s.mean_score,
            'lon': float(s.lon),
            'lat': float(s.lat)
        } for s in query.all()]
        
        # Get enrollment trends (last 12 months)
        enrollment_trends = {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'values': [enrollment_stats['total_enrollment']] * 12  # Placeholder, replace with actual historical data
        }
        
        # Get school types distribution
        school_types_stats = session.query(
            School.school_type,
            func.count(School.id)
        ).group_by(School.school_type).all()
        
        school_types_data = {
            'labels': [t[0] or 'Unknown' for t in school_types_stats],
            'values': [int(t[1]) for t in school_types_stats]
        }
        
        return jsonify({
            'totalSchools': performance_stats['total_schools'],
            'totalStudents': enrollment_stats['total_enrollment'],
            'avgPerformance': performance_stats['average_performance_index'],
            'teacherRatio': resource_stats['teacher_student_ratio'],
            'schools': schools,
            'enrollmentTrends': enrollment_trends,
            'schoolTypes': school_types_data,
            'resources': {
                'teachers': resource_stats['average_teachers'],
                'classrooms': resource_stats['average_classrooms'],
                'labs': resource_stats['average_labs'],
                'libraries': resource_stats['average_libraries']
            },
            'facilities': facility_stats,
            'incidents': incident_stats,
            'staffing': staff_stats,
            'coverage': coverage_stats
        })
    finally:
        session.close()


@app.route('/schools/coverage')
def page_coverage():
    """Render the school coverage (Voronoi) analysis page."""
    center = [-1.286389, 36.817223]
    zoom = 7
    return render_template('voronoi.html', center=center, zoom=zoom)


@app.route('/schools/search')
def schools_search():
    """Search schools by name (partial match). If `external=1` is provided and no local
    matches are found, the server will query Nominatim and return results as extra features.
    Returns a GeoJSON FeatureCollection with source property indicating 'db' or 'nominatim'.
    """
    term = (request.args.get('term') or '').strip()
    external = request.args.get('external', '0') == '1'
    try:
        limit = int(request.args.get('limit', 50))
    except Exception:
        limit = 50

    if not term:
        return jsonify({"type": "FeatureCollection", "features": []})

    session = get_session()
    try:
        like = f"%{term}%"
        # attempt to use both trigram similarity and optional spatial proximity
        lon = request.args.get('lon')
        lat = request.args.get('lat')
        try:
            lon_f = float(lon) if lon is not None else None
            lat_f = float(lat) if lat is not None else None
        except Exception:
            lon_f = lat_f = None

        sim_weight = float(request.args.get('sim_weight') or 0.7)
        dist_weight = float(request.args.get('dist_weight') or 0.3)
        # scale distance in meters where scale_m ~ 1000 gives 1/(1 + d/1000) behavior
        scale_m = float(request.args.get('scale_m') or 1000.0)
        min_score = float(request.args.get('min_score') or 0.03)

        features = []

        if lon_f is not None and lat_f is not None:
            # combine similarity and distance into a final_score
            sql = text(
                """
                SELECT id, name, properties, ST_AsGeoJSON(geom)::json AS geojson,
                       greatest(COALESCE(word_similarity(name, :term),0), COALESCE(similarity(properties->>'NAME', :term),0)) AS sim,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m,
                       (
                           (greatest(COALESCE(word_similarity(name, :term),0), COALESCE(similarity(properties->>'NAME', :term),0)) * :sim_weight)
                           +
                           ((1.0 / (1.0 + (ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / :scale_m))) * :dist_weight)
                       ) AS final_score
                FROM schools
                WHERE (name ILIKE :like OR properties->>'NAME' ILIKE :like)
                ORDER BY final_score DESC NULLS LAST
                LIMIT :limit
                """
            )
            res = session.execute(sql, {"term": term, "like": like, "limit": limit, "lon": lon_f, "lat": lat_f, "sim_weight": sim_weight, "dist_weight": dist_weight, "scale_m": scale_m})
            rows = res.mappings().all()

            for r in rows:
                props = r.get('properties') or {}
                if r.get('name') and not props.get('name'):
                    props['name'] = r.get('name')
                props['score'] = float(r.get('final_score') or 0.0)
                # attach raw sim and distance for debugging/inspection
                props['sim'] = float(r.get('sim') or 0.0)
                props['distance_m'] = float(r.get('distance_m') or 0.0)
                props['source'] = 'db'
                if props['score'] >= min_score:
                    features.append({
                        "type": "Feature",
                        "properties": props,
                        "geometry": r.get('geojson'),
                        "id": r.get('id'),
                    })
        else:
            # fallback: similarity-only ranking
            sql = text(
                """
                SELECT id, name, properties, ST_AsGeoJSON(geom)::json AS geojson,
                       greatest(COALESCE(word_similarity(name, :term),0), COALESCE(similarity(properties->>'NAME', :term),0)) AS final_score
                FROM schools
                WHERE name ILIKE :like OR properties->>'NAME' ILIKE :like
                ORDER BY final_score DESC NULLS LAST
                LIMIT :limit
                """
            )
            res = session.execute(sql, {"term": term, "like": like, "limit": limit})
            rows = res.mappings().all()
            for r in rows:
                props = r.get('properties') or {}
                if r.get('name') and not props.get('name'):
                    props['name'] = r.get('name')
                props['score'] = float(r.get('final_score') or 0.0)
                props['source'] = 'db'
                if props['score'] >= min_score:
                    features.append({
                        "type": "Feature",
                        "properties": props,
                        "geometry": r.get('geojson'),
                        "id": r.get('id'),
                    })

        # If no local results and external requested, call Nominatim (cached)
        if not features and external:
            # perform or return cached nominatim results
            q = term
            nom_results = None
            try:
                with cache_lock:
                    nom_results = nominatim_cache.get(q)
                if nom_results is None:
                    import requests
                    r = requests.get(
                        'https://nominatim.openstreetmap.org/search',
                        params={
                            'q': q,
                            'format': 'json',
                            'limit': 10,
                            'polygon_geojson': 1,
                            'addressdetails': 1,
                        },
                        headers={'User-Agent': 'flask-app-deploy/1.0 (example@example.com)'} ,
                        timeout=10,
                    )
                    nom_results = r.json()
                    with cache_lock:
                        nominatim_cache[q] = nom_results
                        save_cache()
            except Exception:
                nom_results = nom_results or []

            for item in (nom_results or []):
                geom = item.get('geojson')
                # some nominatim items may not include geojson geometry; skip those
                if not geom:
                    continue
                props = {
                    'display_name': item.get('display_name'),
                    'osm_id': item.get('osm_id'),
                    'class': item.get('class'),
                    'type': item.get('type'),
                    'source': 'nominatim',
                    'name': item.get('display_name'),
                }
                features.append({
                    'type': 'Feature',
                    'properties': props,
                    'geometry': geom,
                    'id': f"nominatim-{item.get('osm_id')}",
                })

        return jsonify({"type": "FeatureCollection", "features": features})
    finally:
        session.close()
    if not term:
        return jsonify({"type": "FeatureCollection", "features": []})

    session = get_session()
    try:
        # search name column or properties JSON for partial matches (case-insensitive)
        sql = text(
            "SELECT id, name, properties, ST_AsGeoJSON(geom) AS geojson "
            "FROM schools "
            "WHERE COALESCE(name, '') ILIKE :p OR COALESCE(properties->>'NAME','') ILIKE :p "
            "LIMIT 50"
        )
        p = f"%{term}%"
        rows = session.execute(sql.bindparams(p=p)).all()
        features = []
        for r in rows:
            geom_json = r.geojson
            geometry = None
            if geom_json:
                try:
                    geometry = json.loads(geom_json)
                except Exception:
                    geometry = None
            props = r.properties or {}
            if r.name and not props.get('name'):
                props['name'] = r.name
            props['source'] = 'db'
            features.append({"type": "Feature", "id": r.id, "properties": props, "geometry": geometry})

        if not features and include_external:
            # Query Nominatim (GeoJSON) for the term with keyword 'school' to bias results
            try:
                key = term.lower()
                # check cache first
                cached = nominatim_cache.get(key)
                if cached:
                    for feat in cached:
                        props = feat.get('properties', {})
                        props['source'] = 'nominatim'
                        features.append({"type": "Feature", "id": props.get('osm_id'), "properties": props, "geometry": feat.get('geometry')})
                else:
                    nom_url = 'https://nominatim.openstreetmap.org/search'
                    params = {'q': f"{term} school", 'format': 'geojson', 'limit': 5}
                    resp = requests.get(nom_url, params=params, headers={'User-Agent': 'flask-app-deploy/1.0'}, timeout=5)
                    if resp.status_code == 200:
                        gj = resp.json()
                        feats = []
                        for feat in gj.get('features', []):
                            props = feat.get('properties', {})
                            props['source'] = 'nominatim'
                            features.append({"type": "Feature", "id": props.get('osm_id'), "properties": props, "geometry": feat.get('geometry')})
                            feats.append(feat)
                        # cache results
                        try:
                            nominatim_cache[key] = feats
                            save_cache()
                        except Exception:
                            pass
            except Exception:
                pass

        return jsonify({"type": "FeatureCollection", "features": features})
    finally:
        session.close()


@app.route('/schools/add', methods=['POST'])
def schools_add():
    """Add a GeoJSON Feature into the schools table. Expected JSON body: {"feature": <GeoJSON Feature>}.
    Returns the created record as a GeoJSON feature with assigned id.
    """
    data = request.get_json(silent=True)
    if not data or 'feature' not in data:
        return jsonify({"error": "POST JSON with 'feature' required"}), 400

    feat = data['feature']
    props = feat.get('properties') or {}
    geom = feat.get('geometry')
    if not geom:
        return jsonify({"error": "feature.geometry required"}), 400

    try:
        shapely_geom = shapely_shape(geom)
        wkt = WKTElement(shapely_geom.wkt, srid=4326)
    except Exception as e:
        return jsonify({"error": f"invalid geometry: {e}"}), 400

    name = props.get('name') or props.get('NAME') or props.get('display_name')
    session = get_session()
    try:
        # deduplicate: if an existing feature exists within 50 meters of the geometry, return it instead
        try:
            # compute centroid for non-point geometries
            if geom.get('type') == 'Point' and isinstance(geom.get('coordinates'), (list, tuple)):
                lon_c, lat_c = geom['coordinates'][0], geom['coordinates'][1]
            else:
                centroid = shapely_shape(geom).centroid
                lon_c, lat_c = float(centroid.x), float(centroid.y)
        except Exception:
            lon_c, lat_c = None, None

        if lon_c is not None:
            dup_sql = text(
                "SELECT id, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as dist "
                "FROM schools WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius) "
                "ORDER BY dist LIMIT 1"
            )
            radius_m = 50.0
            dup = session.execute(dup_sql.bindparams(lon=lon_c, lat=lat_c, radius=radius_m)).first()
            if dup:
                return jsonify({"duplicate": True, "existing_id": dup.id}), 200

        school = School(name=name, properties=props, geom=wkt)
        session.add(school)
        session.commit()
        # return created feature
        return jsonify({"type": "Feature", "id": school.id, "properties": props, "geometry": geom})
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route('/schools/<int:school_id>')
def school_get(school_id: int):
    """Return a single school feature by id."""
    session = get_session()
    try:
        sql = text(
            "SELECT id, name, properties, ST_AsGeoJSON(geom) AS geojson FROM schools WHERE id = :id"
        )
        row = session.execute(sql.bindparams(id=school_id)).first()
        if not row:
            return jsonify({"error": "not found"}), 404
        geom = None
        if row.geojson:
            try:
                geom = json.loads(row.geojson)
            except Exception:
                geom = None
        props = row.properties or {}
        if row.name and not props.get('name'):
            props['name'] = row.name
        return jsonify({"type": "Feature", "id": row.id, "properties": props, "geometry": geom})
    finally:
        session.close()


if __name__ == '__main__':
    app.run(debug=True)
