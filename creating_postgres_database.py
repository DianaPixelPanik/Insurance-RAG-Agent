import psycopg2
import os
from dotenv import load_dotenv
from datetime import date

load_dotenv()

conn_params = {
    "dbname": os.getenv("PG_DB_NAME"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASSWORD"),
    "host": os.getenv("PG_HOST"),
    "port": os.getenv("PG_PORT"),
}


def create_insurance_table_with_data():
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_insurance (
            customer_id SERIAL PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            date_of_birth DATE NOT NULL,
            gender VARCHAR(10),
            email VARCHAR(100),
            phone_number VARCHAR(20),
            address VARCHAR(100),
            city VARCHAR(50),
            state VARCHAR(50),
            zip_code VARCHAR(20),

            policy_id VARCHAR(50) UNIQUE NOT NULL,
            policy_type TEXT[] NOT NULL CHECK (
                array_length(policy_type, 1) >= 1 AND
                policy_type::text[] <@ ARRAY['Life Insurance', 'Home Insurance', 'Auto Insurance']::text[]
            ),
            policy_number VARCHAR(50) UNIQUE NOT NULL,
            policy_start_date DATE NOT NULL,
            policy_end_date DATE,
            premium_amount DECIMAL(10,2) NOT NULL,

            agent_id VARCHAR(50),
            agent_name VARCHAR(100),
            agent_email VARCHAR(100),
            agent_phone_number VARCHAR(20),

            claim_date DATE,
            claim_amount DECIMAL(10,2),
            claim_status VARCHAR(20) CHECK (claim_status IN ('Pending', 'Approved', 'Rejected', NULL)),

            payment_id VARCHAR(50),
            payment_date DATE,
            payment_amount DECIMAL(10,2),
            payment_method VARCHAR(50) CHECK (payment_method IN ('Credit Card', 'Bank Transfer', NULL)),

            life_beneficiary_name VARCHAR(100),
            life_beneficiary_relationship VARCHAR(50),
            life_policy_term INTEGER,
            life_sum_assured DECIMAL(12,2),

            home_property_address VARCHAR(100),
            home_property_value DECIMAL(12,2),
            home_property_type VARCHAR(50) CHECK (home_property_type IN ('Single Family', 'Condo', 'Apartment', NULL)),
            home_coverage_type VARCHAR(50) CHECK (home_coverage_type IN ('Building', 'Contents', 'Liability', NULL)),

            auto_vehicle_make VARCHAR(50),
            auto_vehicle_model VARCHAR(50),
            auto_vehicle_year INTEGER,
            auto_coverage_type VARCHAR(50) CHECK (auto_coverage_type IN ('Liability', 'Collision', 'Comprehensive', NULL))
        )
        """)

        sample_data = [
            # Customer 1: Life Insurance only
            (
                'John', 'Smith', date(1980, 5, 15), 'Male', 'john.smith@email.com', '555-123-4567',
                '123 Main St', 'Boston', 'MA', '02108',
                'POL-1001', ['Life Insurance'], 'LIFE-001', date(2020, 1, 1), date(2040, 1, 1), 150.00,
                'AGT-001', 'Sarah Johnson', 'sarah.j@insure.com', '555-987-6543',
                None, None, None,
                'PAY-001', date(2023, 1, 1), 150.00, 'Credit Card',
                'Mary Smith', 'Spouse', 20, 500000.00,
                None, None, None, None,
                None, None, None, None
            ),
            # Customer 2: Home Insurance only
            (
                'Emily', 'Davis', date(1975, 8, 22), 'Female', 'emily.davis@email.com', '555-234-5678',
                '456 Oak Ave', 'Chicago', 'IL', '60601',
                'POL-1002', ['Home Insurance'], 'HOME-001', date(2021, 3, 15), date(2024, 3, 15), 85.50,
                'AGT-002', 'Michael Brown', 'michael.b@insure.com', '555-876-5432',
                date(2022, 5, 10), 2500.00, 'Approved',
                'PAY-002', date(2023, 3, 15), 85.50, 'Bank Transfer',
                None, None, None, None,
                '456 Oak Ave, Chicago, IL', 350000.00, 'Single Family', 'Building',
                None, None, None, None
            ),
            # Customer 3: Auto Insurance only
            (
                'Robert', 'Johnson', date(1990, 11, 5), 'Male', 'robert.j@email.com', '555-345-6789',
                '789 Pine Rd', 'Houston', 'TX', '77002',
                'POL-1003', ['Auto Insurance'], 'AUTO-001', date(2022, 6, 1), date(2023, 6, 1), 120.75,
                'AGT-003', 'Lisa Williams', 'lisa.w@insure.com', '555-765-4321',
                None, None, None,
                'PAY-003', date(2023, 6, 1), 120.75, 'Credit Card',
                None, None, None, None,
                None, None, None, None,
                'Toyota', 'Camry', 2018, 'Comprehensive'
            ),
            # Customer 4: Life and Auto Insurance
            (
                "Alice", "Brown", date(1985, 7, 10), "Female", "alice.b@email.com", "555-111-2222",
                "111 Pine St", "New York", "NY", "10001",
                "POL-1004", ["Life Insurance", "Auto Insurance"], "LA-002", date(2023, 1, 15), date(2043, 1, 15), 275.50,
                "AGT-001", "Sarah Johnson", "sarah.j@insure.com", "555-987-6543",
                None, None, None,
                "PAY-004", date(2023, 1, 15), 275.50, "Credit Card",
                "Bob Brown", "Spouse", 20, 400000.00,
                None, None, None, None,
                "Honda", "Civic", 2020, "Collision"
            ),
            # Customer 5: Home and Auto Insurance
            (
                "Charlie", "Green", date(1992, 3, 25), "Male", "charlie.g@email.com", "555-333-4444",
                "333 Oak Ln", "Los Angeles", "CA", "90001",
                "POL-1005", ["Home Insurance", "Auto Insurance"], "HA-003", date(2022, 10, 1), date(2025, 10, 1), 160.20,
                "AGT-002", "Michael Brown", "michael.b@insure.com", "555-876-5432",
                None, None, None,
                "PAY-005", date(2023, 10, 1), 160.20, "Bank Transfer",
                None, None, None, None,
                "333 Oak Ln, Los Angeles, CA", 600000.00, "Condo", "Contents",
                "Tesla", "Model 3", 2022, "Comprehensive"
            ),
            # Customer 6: Life, Home, and Auto Insurance
            (
                "Diana", "Miller", date(1988, 9, 8), "Female", "diana.m@email.com", "555-555-6666",
                "555 Maple Ave", "Dallas", "TX", "75201",
                "POL-1006", ["Life Insurance", "Home Insurance", "Auto Insurance"], "LHA-004", date(2024, 2, 1), date(2044, 2, 1), 320.00,
                "AGT-003", "Lisa Williams", "lisa.w@insure.com", "555-765-4321",
                None, None, None,
                "PAY-006", date(2024, 2, 1), 320.00, "Credit Card",
                "David Miller", "Spouse", 20, 750000.00,
                "555 Maple Ave, Dallas, TX", 450000.00, "Single Family", "Building",
                "Ford", "F-150", 2021, "Liability"
            ),
        ]

        cur.execute("SELECT COUNT(*) FROM customer_insurance")
        if cur.fetchone()[0] == 0:
            cur.executemany("""
            INSERT INTO customer_insurance (
                first_name, last_name, date_of_birth, gender, email, phone_number,
                address, city, state, zip_code,
                policy_id, policy_type, policy_number, policy_start_date, policy_end_date, premium_amount,
                agent_id, agent_name, agent_email, agent_phone_number,
                claim_date, claim_amount, claim_status,
                payment_id, payment_date, payment_amount, payment_method,
                life_beneficiary_name, life_beneficiary_relationship, life_policy_term, life_sum_assured,
                home_property_address, home_property_value, home_property_type, home_coverage_type,
                auto_vehicle_make, auto_vehicle_model, auto_vehicle_year, auto_coverage_type
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """, sample_data)
            print(f"Inserted {len(sample_data)} sample records")
        else:
            print("Table already contains data — skipping sample insert")

        conn.commit()
        print("Insurance table ready.")

    except Exception as error:
        print(f"Error: {error}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_insurance_data_for_embeddings():
    """Retrieve data formatted for embedding generation."""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        cur.execute("""
        SELECT
            customer_id::text,
            first_name || ' ' || last_name AS customer_name,
            array_to_string(policy_type, ', ') AS policy_types,
            policy_number,
            date_of_birth::text,
            email,
            phone_number,
            address || ', ' || city || ', ' || state || ' ' || zip_code AS full_address,
            premium_amount::text,
            COALESCE(life_beneficiary_name, '') AS life_beneficiary,
            COALESCE(life_sum_assured::text, '') AS life_sum_assured,
            COALESCE(home_property_address, '') AS home_address,
            COALESCE(home_property_value::text, '') AS home_value,
            COALESCE(home_property_type, '') AS home_type,
            COALESCE(auto_vehicle_make || ' ' || auto_vehicle_model, '') AS vehicle,
            COALESCE(auto_vehicle_year::text, '') AS vehicle_year
        FROM customer_insurance
        """)

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    except Exception as error:
        print(f"Error retrieving data: {error}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    create_insurance_table_with_data()
