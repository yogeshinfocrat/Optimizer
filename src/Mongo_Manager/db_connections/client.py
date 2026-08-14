import os
from fastapi import Request
from pymongo import MongoClient

_mongo_client = None

def get_mongo_client(request: Request):
    '''Gets the MongoDB client. Creates it if it doesn't exist.'''
    '''This is not used, but leaving it here for reference in case we
    need to use pymongo client instead of mongoengine.'''
    global _mongo_client
    if _mongo_client is None:
        MONGO_ROUTING_DB_PATH = os.getenv("MONGO_ROUTING_DB_PATH", "mongodb://127.0.0.1:27017/transformer")
        _mongo_client = MongoClient(MONGO_ROUTING_DB_PATH)
    return _mongo_client