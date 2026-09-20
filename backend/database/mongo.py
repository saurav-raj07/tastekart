import os

from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "tastekart")

mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
database = mongo_client[MONGO_DB_NAME]

users = database.users
restaurants_collection = database.restaurants
menu_items = database.menu_items
orders = database.orders
partners = database.partners
admins = database.admins
sessions = database.sessions
