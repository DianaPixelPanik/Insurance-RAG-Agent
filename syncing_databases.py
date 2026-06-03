"""
Real-time sync: PostgreSQL → Milvus via LISTEN/NOTIFY.
Run this as a background process alongside backend_app.py.
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import openai
from pymilvus import connections, Collection
import json
import time
import os
from threading import Timer, Event, Thread, Lock
from dotenv import load_dotenv

load_dotenv()

required_vars = ["PG_DB_NAME", "PG_USER", "PG_PASSWORD", "PG_HOST", "PG_PORT", "OPENAI_API_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

conn_params = {
    "dbname": os.getenv("PG_DB_NAME"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASSWORD"),
    "host": os.getenv("PG_HOST"),
    "port": os.getenv("PG_PORT"),
}

openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    conn = psycopg2.connect(**conn_params)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Create trigger function
    cur.execute("""
        CREATE OR REPLACE FUNCTION notify_insurance_change() RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('insurance_change', row_to_json(NEW)::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on customer_insurance table
    cur.execute("""
        CREATE OR REPLACE TRIGGER insurance_change_trigger
        AFTER INSERT OR UPDATE ON customer_insurance
        FOR EACH ROW EXECUTE FUNCTION notify_insurance_change();
    """)

    cur.execute("LISTEN insurance_change;")

    connections.connect("default", host=os.getenv("MILVUS_HOST", "localhost"), port=os.getenv("MILVUS_PORT", "19530"))
    collection = Collection("insurance_customers")

    notifications = []
    notifications_lock = Lock()
    stop_event = Event()

    def get_embedding(text: str):
        try:
            response = openai.embeddings.create(
                input=text,
                model="text-embedding-3-large",
                dimensions=1536,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    def process_notifications():
        with notifications_lock:
            batch = notifications.copy()
            notifications.clear()

        if batch:
            print(f"Processing {len(batch)} notifications")
            seen = set()
            for notify in batch:
                try:
                    data = json.loads(notify.payload)
                    record_id = data.get("customer_id")
                    if record_id in seen:
                        continue
                    seen.add(record_id)

                    text = (
                        f"{data.get('first_name','')} {data.get('last_name','')} "
                        f"{data.get('policy_type','')} "
                        f"premium={data.get('premium_amount','')}"
                    )
                    embedding = get_embedding(text)
                    if embedding:
                        collection.delete(f'customer_id == "{record_id}"')
                        collection.insert([[str(record_id)], [embedding], [""], [""], [{}]])
                        collection.flush()
                        print(f"Updated embedding for customer_id={record_id}")
                except Exception as e:
                    print(f"Error processing notification: {e}")

        if not stop_event.is_set():
            Timer(5, process_notifications).start()

    def listen_for_stop():
        while not stop_event.is_set():
            cmd = input()
            if cmd.strip().lower() == "stop":
                stop_event.set()

    process_notifications()
    stop_thread = Thread(target=listen_for_stop, daemon=True)
    stop_thread.start()

    print("Listening for database changes on 'insurance_change'... (type 'stop' to exit)")
    while not stop_event.is_set():
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            with notifications_lock:
                notifications.append(notify)
        time.sleep(0.1)

except Exception as e:
    print(f"Error: {e}")
finally:
    stop_event.set()
    if "cur" in locals():
        cur.close()
    if "conn" in locals():
        conn.close()
    connections.disconnect("default")
    print("Sync process stopped.")
