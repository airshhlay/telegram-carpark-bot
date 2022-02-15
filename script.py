data = {}
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

# with open('./shoppingmall_out.json', 'r') as f:
#   data = json.load(f)

# with open('./hdb_out.json', 'r') as f:
#   data = json.load(f)
  
  
# keys = ['type_of_parking_system', 'short_term_parking', 'free_parking', 'night_parking']
# keys_renamed = ['PARKING SYSTEM: ', 'SHORT-TERM PARKING: ', 'FREE PARKING: ', 'NIGHT PARKING: ']
# for item in data:
#   # rates = []
#   # for index, key in enumerate(keys):
#   #   print(key)
#   #   val = item[key]
#   #   del item[key]
#   #   if val == "NO" or val == "YES":
#   #     continue
#   #   print(val)
#   #   rates.append(keys_renamed[index] + val)
#   # item['rates'] = rates
#   item['type'] = 'hdb'

# with open('./hdb_out.json', 'w') as f:
#   json.dump(data, f)
  
  
# with open('./shoppingmall_out.json', 'w') as f:
#   json.dump(data, f)
  

client = pymongo.MongoClient(MONGO_CONNECTION_STR.format(mongoUser=MONGO_USERNAME, mongoPwd=MONGO_PWD, databaseName=DATABASE_NAME))

db = client[DATABASE_NAME]
botCollection = db[BOT_COLLECTION]

# load carpark data
carparkDataDoc = botCollection.find_one({'name': 'carparkData'})
carparkData = carparkDataDoc.get('data')
print(type(carparkData))
# with open('./hdb_out.json', 'r') as f:
#   data = json.load(f)
  
# with open('./shoppingmall_out.json', 'r') as f:
#   data += json.load(f)

with open('./out.json', 'r') as f:
  carparkData = json.load(f)
coordConverter = SVY21()
for item in carparkData:
  if 'lat' in item or 'lon' in item:
    del item['lat']
    del item['lon']
  if item["type"] == 'shopping_mall':
    lat = item['latitude']
    lon = item['longitude']
    x_coord, y_coord = coordConverter.computeSVY21(lat, lon)
    item['x_coord'] = x_coord
    item['y_coord'] = y_coord
    
    # newRates = []
    # for index, rate in enumerate(item['rates']):
    #   title, text = rate.split(":")[0].strip(),rate.split(":")[1].strip()
    #   newRates.append({title: text})

    # item['rates'] = newRates
    
    dictionary = item["rates"][1]
    if "MON-FRI (before 5,6pm)" in dictionary:
      item["rates"][1] = {"MON-FRI (after 5,6pm)": dictionary["MON-FRI (before 5,6pm)"]}
  # else:
  #   x_coord = item['x_coord']
  #   y_coord = item['y_coord']
  #   lat, lon = coordConverter.computeLatLon(x_coord, y_coord)
  #   item['latitude'] = lat
  #   item['longitude'] = lon
  #   newRates = []
  #   for rate in item['rates']:
  #     title, text = rate.split(":")[0].strip().title(),rate.split(":")[1].strip().lower()
  #     newRates.append({title: text})
  #   item['rates'] = newRates

# with open('./out.json', 'r') as f:
#   data = json.load(f)
  
# for item in data:
#   if item['type'] == 'shopping_mall':
#     rates = 
# with open("./hdb_out.json", 'w') as f:
#   json.dump(data, f)

with open('./shoppingmall_out.json', 'w') as f:
  json.dump(carparkData, f)

# botCollection.update_one({"_id": carparkDataDoc['_id']}, {'$set': {"data": carparkData}})