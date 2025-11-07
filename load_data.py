"""
Script to load GeoJSON from data/sec.geojson into PostGIS.

Usage:
  python load_data.py

Requirements:
  - A PostgreSQL database `schools_ke` accessible at the URL configured in `db.py`.
  - The PostGIS extension enabled (the script will try to enable it if allowed).
"""
import json
from sqlalchemy import text
from shapely.geometry import shape
from geoalchemy2 import WKTElement

from db import engine, SessionLocal, Base
from models import School


def enable_postgis():
    # Create extension if possible
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            print("Ensured PostGIS extension exists (if allowed).")
        except Exception as e:
            print("Warning: could not create PostGIS extension:", e)


def create_schema():
    # Create tables from models
    Base.metadata.create_all(bind=engine)
    print("Created tables (if not existing)")
    # Create a spatial index on the geometry column for faster spatial queries
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS schools_geom_gist ON schools USING GIST (geom);"))
            print("Ensured spatial GIST index on schools.geom")
    except Exception as e:
        print("Warning: could not create spatial index:", e)
    # Create pg_trgm extension and trigram indexes for fuzzy/name search
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS schools_name_trgm ON schools USING GIN (name gin_trgm_ops);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS schools_props_name_trgm ON schools USING GIN ((properties->>'NAME') gin_trgm_ops);"))
            print("Ensured pg_trgm and trigram GIN indexes on name and properties->>'NAME'")
    except Exception as e:
        print("Warning: could not create trigram indexes:", e)


def load_geojson(path="data/sec.geojson"):
    session = SessionLocal()
    try:
        with open(path, "r", encoding="utf-8") as f:
            gj = json.load(f)

        features = gj.get("features") or []
        print(f"Loading {len(features)} features...")

        for feat in features:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not geom:
                continue
            shapely_geom = shape(geom)
            wkt = WKTElement(shapely_geom.wkt, srid=4326)

            name = props.get("name") or props.get("NAME") or props.get("Name")
            school = School(name=name, properties=props, geom=wkt)
            session.add(school)

        session.commit()
        print("Inserted features into the database.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main():
    enable_postgis()
    create_schema()
    load_geojson()


if __name__ == "__main__":
    main()
