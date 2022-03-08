
import json
import os
import re

import pymongo
from svy21 import SVY21
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

svy21 = SVY21()

checkPassed = True
for item in data:
  if "x_coord" not in item and "latitude" not in item:
    print("FAILURE - missing coordinates for " + str(item))
    checkPassed = False
    continue
  if "x_coord" not in item:
    x, y = svy21.computeSVY21(item.get("latitude"), item.get("longitude"))
    data["x_coord"], data["y_coord"] = x, y
  if "latitude" not in item:
    lat, lon = svy21.computeLatLon(item.get('x_coord'), item.get('y_coord'))
    data["latitude"], data["longitude"] = lat, lon

if checkPassed:
  botCollection.update_one({"_id": carparkDataDoc['_id']}, {'$set': {"data": data}})
  with open('./out.json', 'w') as f:
    json.dump(data, f)