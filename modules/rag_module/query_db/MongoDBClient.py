# query_db/MongoDBClient.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class MongoDBClient:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB_NAME")

        if not mongo_uri or not mongo_db_name:
            raise ValueError("Missing MONGO_URI or MONGO_DB_NAME in environment variables.")

        self.client = MongoClient(mongo_uri)
        self.db = self.client[mongo_db_name]

    def insert_one(self, collection_name: str, document: dict):
        result = self.db[collection_name].insert_one(document)
        return result.inserted_id

    def insert_many(self, collection_name: str, documents: list[dict]):
        """Insert multiple documents."""
        result = self.db[collection_name].insert_many(documents)
        return result.inserted_ids
