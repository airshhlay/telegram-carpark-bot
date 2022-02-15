
import json
import os
import re

import pymongo
MONGO_CONNECTION_STR = "mongodb+srv://{mongoUser}:{mongoPwd}@cluster0.up9mp.mongodb.net/{databaseName}?retryWrites=true&w=majority"
MONGO_USERNAME = os.environ.get("MONGO_USERNAME", "wheretoparksg")
MONGO_PWD = os.environ.get("MONGO_PWD", "C7vQCxgilPugEvyf")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "wheretoparksg")
BOT_COLLECTION = os.environ.get("BOT_COLLECTION_NAME", "parkingbot")


client = pymongo.MongoClient(MONGO_CONNECTION_STR.format(mongoUser=MONGO_USERNAME, mongoPwd=MONGO_PWD, databaseName=DATABASE_NAME))

db = client[DATABASE_NAME]
botCollection = db[BOT_COLLECTION]

# load carpark data
carparkDataDoc = botCollection.find_one({'name': 'carparkData'})

data = {}
with open('./carparks.json', 'r') as f:
  data = json.load(f)


botCollection.update_one({"_id": carparkDataDoc['_id']}, {'$set': {"data": data}})