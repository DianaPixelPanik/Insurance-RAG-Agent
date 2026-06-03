import os
import time
from dotenv import load_dotenv
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from openai import OpenAI
from creating_postgres_database import get_insurance_data_for_embeddings

load_dotenv()

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "insurance_customers"
DIMENSION = 1536  # text-embedding-3-large default


def create_milvus_collection() -> Collection:
    if utility.has_collection(COLLECTION_NAME):
        utility.drop_collection(COLLECTION_NAME)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="customer_id", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION),
        FieldSchema(name="customer_name", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="policy_types", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]

    schema = CollectionSchema(fields, description="Insurance customer embeddings")
    collection = Collection(COLLECTION_NAME, schema)
    collection.create_index(
        "embedding",
        {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}},
    )
    return collection


def generate_embeddings(data: list) -> list:
    """Generate OpenAI embeddings for each customer record."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    texts = []
    for record in data:
        parts = [
            f"Customer: {record['customer_name']}",
            f"Policies: {record['policy_types']}",
            f"Premium: ${record['premium_amount']}",
        ]
        if record["life_beneficiary"]:
            parts.append(
                f"Life Beneficiary: {record['life_beneficiary']} (${record['life_sum_assured']})"
            )
        if record["home_address"]:
            parts.append(
                f"Home: {record['home_address']} ({record['home_type']}, ${record['home_value']})"
            )
        if record["vehicle"]:
            parts.append(f"Vehicle: {record['vehicle']} ({record['vehicle_year']})")
        texts.append("\n".join(parts))

    embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        response = client.embeddings.create(
            input=texts[i : i + batch_size],
            model="text-embedding-3-large",
            dimensions=DIMENSION,
        )
        embeddings.extend([e.embedding for e in response.data])
        time.sleep(1)

    return embeddings


def main():
    insurance_data = get_insurance_data_for_embeddings()
    if not insurance_data:
        print("No data retrieved from PostgreSQL")
        return

    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    collection = create_milvus_collection()

    print("Generating embeddings...")
    embeddings = generate_embeddings(insurance_data)

    print("Inserting into Milvus...")
    entities = [
        [item["customer_id"] for item in insurance_data],
        embeddings,
        [item["customer_name"] for item in insurance_data],
        [item["policy_types"] for item in insurance_data],
        [
            {
                "email": item["email"],
                "phone": item["phone_number"],
                "address": item["full_address"],
                "dob": item["date_of_birth"],
                "life_beneficiary": item["life_beneficiary"],
                "life_sum_assured": item["life_sum_assured"],
                "home_address": item["home_address"],
                "home_value": item["home_value"],
                "vehicle": item["vehicle"],
                "vehicle_year": item["vehicle_year"],
            }
            for item in insurance_data
        ],
    ]

    collection.insert(entities)
    collection.flush()
    print(f"Inserted {len(insurance_data)} embeddings into Milvus")


if __name__ == "__main__":
    main()
