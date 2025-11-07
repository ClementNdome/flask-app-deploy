from sqlalchemy import text
from db import engine

def upgrade_database():
    """
    Upgrade the database schema to support enhanced education management features.
    """
    commands = [
        # Enable required extensions
        "CREATE EXTENSION IF NOT EXISTS postgis;",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
        
        # Create new tables
        """
        CREATE TABLE IF NOT EXISTS programs (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            level VARCHAR
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS school_programs (
            school_id INTEGER REFERENCES schools(id),
            program_id INTEGER REFERENCES programs(id),
            PRIMARY KEY (school_id, program_id)
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS facilities (
            id SERIAL PRIMARY KEY,
            school_id INTEGER REFERENCES schools(id),
            name VARCHAR NOT NULL,
            type VARCHAR,
            condition VARCHAR,
            last_maintenance DATE
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS staff (
            id SERIAL PRIMARY KEY,
            school_id INTEGER REFERENCES schools(id),
            name VARCHAR NOT NULL,
            role VARCHAR,
            qualifications JSONB,
            joining_date DATE
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id SERIAL PRIMARY KEY,
            school_id INTEGER REFERENCES schools(id),
            type VARCHAR,
            description TEXT,
            severity VARCHAR,
            status VARCHAR,
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
        """,

        """
        -- Time-series and auth tables
        CREATE TABLE IF NOT EXISTS enrollment_history (
            id SERIAL PRIMARY KEY,
            school_id INTEGER REFERENCES schools(id),
            recorded_at TIMESTAMP NOT NULL,
            enrollment INTEGER,
            capacity INTEGER
        );
        """,

        """
        CREATE TABLE IF NOT EXISTS inspection_history (
            id SERIAL PRIMARY KEY,
            school_id INTEGER REFERENCES schools(id),
            inspected_at TIMESTAMP NOT NULL,
            inspector VARCHAR,
            score FLOAT,
            notes TEXT
        );
        """,

        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR UNIQUE,
            password_hash VARCHAR,
            full_name VARCHAR,
            email VARCHAR UNIQUE,
            active INTEGER DEFAULT 1,
            role VARCHAR DEFAULT 'viewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Add new columns to schools table
        """
        DO $$ 
        BEGIN
            BEGIN
                ALTER TABLE schools 
                    ADD COLUMN code VARCHAR(20) UNIQUE,
                    ADD COLUMN school_type VARCHAR,
                    ADD COLUMN county VARCHAR,
                    ADD COLUMN sub_county VARCHAR,
                    ADD COLUMN ward VARCHAR,
                    ADD COLUMN student_capacity INTEGER,
                    ADD COLUMN current_enrollment INTEGER,
                    ADD COLUMN teacher_count INTEGER,
                    ADD COLUMN staff_count INTEGER,
                    ADD COLUMN classrooms INTEGER,
                    ADD COLUMN labs INTEGER,
                    ADD COLUMN libraries INTEGER,
                    ADD COLUMN computer_labs INTEGER,
                    ADD COLUMN mean_score FLOAT,
                    ADD COLUMN performance_index FLOAT,
                    ADD COLUMN established_date DATE,
                    ADD COLUMN last_inspection_date DATE,
                    ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            EXCEPTION
                WHEN duplicate_column THEN
                    NULL;
            END;
        END $$;
        """,
        
        # Create indexes for performance
        """
        CREATE INDEX IF NOT EXISTS idx_enrollment_history_school ON enrollment_history(school_id);
        CREATE INDEX IF NOT EXISTS idx_inspection_history_school ON inspection_history(school_id);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_schools_code ON schools(code);
        CREATE INDEX IF NOT EXISTS idx_schools_type ON schools(school_type);
        CREATE INDEX IF NOT EXISTS idx_schools_county ON schools(county);
        CREATE INDEX IF NOT EXISTS idx_schools_performance ON schools(performance_index);
        CREATE INDEX IF NOT EXISTS idx_staff_role ON staff(role);
        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
        CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(type);
        """,
    ]
    
    with engine.begin() as conn:
        for command in commands:
            try:
                conn.execute(text(command))
            except Exception as e:
                print(f"Error executing command: {e}")
                raise

if __name__ == "__main__":
    upgrade_database()
    print("Database schema upgraded successfully")