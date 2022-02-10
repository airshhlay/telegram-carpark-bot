"""
Reference: https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/persistentconversationbot.py
"""

from typing import Tuple
import time
import logging
import requests
import json
import json
import re
# import signal
# import sys
from datetime import date, datetime
from math import radians, cos, sin, asin, sqrt
import os
from telegram.error import TelegramError
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove, KeyboardButton,ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    # PicklePersistence,
    CallbackContext,
    CallbackQueryHandler
)
import pymongo
from svy21 import SVY21

PORT = int(os.environ.get("PORT", 5000))
coordConverter = SVY21()
# tokens and access keys
TOKEN, URA_ACCESS_KEY, MY_TRANSPORT_ACCESS_KEY, ONEMAP = None, None, None, {}

# database
db = None
MONGO_CONNECTION_STR = "mongodb+srv://{mongoUser}:{mongoPwd}@cluster0.up9mp.mongodb.net/{databaseName}?retryWrites=true&w=majority"
MONGO_USERNAME = os.environ.get("MONGO_USERNAME", "wheretoparksg")
MONGO_PWD = os.environ.get("MONGO_PWD", "C7vQCxgilPugEvyf")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "wheretoparksg")
BOT_COLLECTION = os.environ.get("BOT_COLLECTION_NAME", "parkingbot")
CARPARK_COLLECTION = os.environ.get("CARPARK_COLLECTION_NAME", "carparks")

CARPARK_RANGE = int(os.environ.get('CARPARK_RANGE', 500))
CARPARK_LIMIT = int(os.environ.get('CARPARK_LIMIT', 3))

carparkData = None
# logger
logger = None


# ======= CONSTANTS USED FOR MESSAGING =====
CHOOSING, INFO_SENT, ADDITIONAL = range(3)

POSTAL_CODE_RECEIVED = "Looking up postal code..."
ADDRESS_RECEIVED = "Looking up address..."

LOOKING_FOR_NEAR = "Looking for carparks near you..."
LOOKING_FOR_ADDRESS = "Looking for carparks near {addr}..."

INVALID_POSTAL_CODE = "An error occured - please double check postal code!\n\n<i>Only Singapore addresses and postal codes are supported\n</i>"
INVALID_ADDRESS = "An error occured - please double check the address!\n\n<i>1. Only Singapore addresses and postal codes are supported\n2. Try refining the address, or use a postal code.</i>"
INVALID_CURRENT_LOCATION = "An error occured - I can only search for carparks for you if you are in Singapore! If you ARE in Singapore, try using an address or a postal code instead."

FALLBACK_MESSAGE = ""

NO_AVAILABLE_PARKING = "No available parking near this address - try a different location?"

CARPARK_FORMAT = """<b>{name}</b>
Distance away: {distance}m

Available lots: {availableLots}
Lot types: {lotType}

Weekday Min: {weekdayTime} mins
Weekday Rate: {weekdayRate}
SatDay Min: {satDayMin} mins
SatDay Rate: {satDayRate}
Sun PH Min: {sunMin} mins
Sun PH Rate: {sunRate}
"""

# ====== methods for external API integration ======
GOOGLEMAPS_URL = {
  "LATLON_FORMAT": "https://www.google.com/maps/place/{lat},{lon}",
  "ADDRESS_FORMAT": "https://www.google.com/maps/place/{address}"
}

URA_API = {
  "FETCH_TOKEN": "https://www.ura.gov.sg/uraDataService/insertNewToken.action"
}

def fetchUraToken():
  today = date.today()
  data = db[BOT_COLLECTION].find_one({'name': 'ura'})
  ura_token_last_regen = data.get("URA_TOKEN_LAST_REGENERATED")
  ura_token = data.get('URA_TOKEN')

  if not URA_ACCESS_KEY:
    raise TelegramError('No URA access key found')

  if not ura_token or not ura_token_last_regen or ura_token_last_regen < date.today:
    # fetch new ura token
    r = doGetRequest(URA_API['FETCH_TOKEN'], {'AccessKey': URA_ACCESS_KEY})
    token = r.get('Result')
    if not token:
      raise TelegramError(f"Error occured when fetching URA token {str(r)}")
    
    data['URA_TOKEN_LAST_REGENERATED'] = today
    data['URA_TOKEN'] = token

    return token
  return ura_token

ONEMAP_API = {
  "SEARCH": "https://developers.onemap.sg/commonapi/search?searchVal={searchVal}&returnGeom=Y&getAddrDetails=Y&pageNum=1",
  "REVERSE_GEOCODE": "https://developers.onemap.sg/privateapi/commonsvc/revgeocode?location={x},{y}&token={token}&addressType=all",
  "GET_TOKEN": "https://developers.onemap.sg/privateapi/auth/post/getToken"
}
def fetchOneMapToken() -> Tuple[str, str]:
  body = {'email': ONEMAP['email'], 'password': ONEMAP['password']}
  r = doPostRequest(ONEMAP_API['GET_TOKEN'], body)
  if r.get('access_token') and r.get('expiry_timestamp'):
    return r.get('access_token'), r.get('expiry_timestamp')
  else:
    logger.error("No token found for OneMap. Exiting....")
    raise Exception()
  
def fetchLocationDataFromAddr(addr: str) -> dict:
  url = ONEMAP_API['SEARCH'].format(searchVal=addr)
  r = doGetRequest(url)
  
  if r and r.get('found') > 0 and r.get("results"):
    return r.get('results')[0]
  
  return None

def fetchLocationDataFromCoord(x: str, y: str) -> dict:
  url = ONEMAP_API['REVERSE_GEOCODE'].format(x=x, y=y, token=ONEMAP['token'])
  r = doGetRequest(url)
  if r and r.get('GeocodeInfo') and len(r.get('GeocodeInfo')) > 0:
    return r.get('GeocodeInfo')[0]
  
  return None

# generic method to make a get request to specified url
# returns the response, or None if error occurs
def doGetRequest(url, headers={'Accept':'application/json'}) -> dict:
  r = requests.get(url, headers=headers, timeout=10)
  try:
    if r.status_code == 200:
      r = r.json()
      logger.info("Url: %s, Response: %s", url, str(r))
      return r
    else:
      r = r.json()
      logger.error("Url: %s, Response: %s", url, str(r))
  except requests.exceptions.Timeout as err:
    logger.error("Request to %s timed out", url)
  except (requests.exceptions.ConnectionError, requests.exceptions.JSONDecodeError):
    logger.info("connection error, retrying")
    # retry once
    time.sleep(3)
    return doGetRequest(url, headers)
  return None
    
def doPostRequest(url, body=None, headers=None) -> dict:
  r = requests.post(url, data=body, headers=headers, timeout=10)
  try:
    if r.status_code == 200:
      r = r.json()
      logger.info("Url: %s, Response: %s", url, str(r))
      return r
    else:
      r = r.json()
      logger.error("Url: %s, Response: %s", url, str(r))
      return None
  except requests.exceptions.Timeout as err:
    logger.error("Request to %s timed out", url)

# ====== General Utility Functions ======
def convertStrToFloat(num: str) -> float:
  try:
    return float(num)
  except:
    logger.error("convertStrToFloat: Conversion to float error | Input: %s", num)
    raise TelegramError(f"Conversion to float error occured for {num}")

# calculate the straight line distance between two X,Y coordinates (SYV21)
def calculateDistanceXY(x1: float, y1: float, x2: float, y2: float) -> float:
  first = (x1 - x2) ** 2
  second = (y1 - y2) ** 2
  distance = (first + second) ** (0.5)
  return round(distance, 2)

# filters for available parking based on the given x y coordinate, and according to the settings (CARPARK_RANGE, CARPARK_LIMIT)
def filterForCarparks(x: str, y: str) -> str:
  xFloat, yFloat = convertStrToFloat(x), convertStrToFloat(y)
  nearbyCarparks = []
  
  for carpark in carparkData:
    distance = calculateDistanceXY(xFloat, yFloat, carpark['x_coord'], carpark['y_coord'])
    if distance <= CARPARK_RANGE:
      carpark['distance'] = distance
      nearbyCarparks.append(carpark)
  
  if len(nearbyCarparks) > 1:
    nearbyCarparks.sort(key=lambda x: x['distance'])
    
  if len(nearbyCarparks) > CARPARK_LIMIT:
      nearbyCarparks =  nearbyCarparks[:CARPARK_LIMIT]
      
  return nearbyCarparks

class Pagination:
  def __init__(self, lst, messageId):
    self.lst = lst
    self.messageId = messageId
    
  def getPage(self, index: int) -> Tuple[str, InlineKeyboardMarkup]:
    carpark = self.lst[index]
    buttons = []
    # has previous page
    if index > 0:
      buttons.append([InlineKeyboardButton(text="< prev", callback_data=f"{self.messageId},{index - 1}")])
  
    # has next page
    if index < len(self.lst) - 1:
      buttons.append([InlineKeyboardButton(text="next >", callback_data=(f"{self.messageId},{index + 1}"))])
      
    # add google maps button
    buttons.append([InlineKeyboardButton(text="Open in Google Maps", url=GOOGLEMAPS_URL['LATLON_FORMAT'].format(lat=carpark['lat'], lon=carpark['lon']))])
    
    buttons.append([InlineKeyboardButton(text="Refresh Availabilities", callback_data=f"{self.messageId}, refresh")])
    return self.formatPageText(carpark), InlineKeyboardMarkup(buttons)
  
  def refreshAvailabilities(self, index: int) -> Tuple[str, InlineKeyboardMarkup]:
    return  
  
  # formats individual carpark information and how it is displayed
  def formatPageText(self, carparkInfo: dict) -> str:
    return CARPARK_FORMAT.format(name=carparkInfo.get('address'), distance=carparkInfo['distance'], availableLots="NIL", lotType="NIL", weekdayTime="NIL", weekdayRate="NIL", satDayMin="NIL", satDayRate="NIL", sunMin="NIL", sunRate="NIL")
  
# creates a Pagination object which consolidates the available parking to into one message for the user
def processCarparkInfo(carparkInfo: list) -> Pagination:
  for carpark in carparkInfo:
    lat, lon = coordConverter.computeLatLon(carpark['x_coord'], carpark['y_coord'])
    carpark['lat'] = lat
    carpark['lon'] = lon

  return carparkInfo
    
# ====== Telegram Markup Keyboards ======
# keyboard buttons
share_current_location_btn = [KeyboardButton(text="Share Current Location", request_location=True)]

# keyboards
# most often used keyboard that includes the share location button
keyboard1 = ReplyKeyboardMarkup([share_current_location_btn], one_time_keyboard=True, input_field_placeholder="Type an address or postal code...")

# ====== Telegram Bot Utility Functions ======
# reply the given message with text and optional keyboard
def replyText(update: Update, text: str, keyboard: ReplyKeyboardMarkup = None):
  return update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
  
# reply the given message with a venue and optional keyboard (?)
def replyVenue(update: Update, text: str, lat: str, lon: str, address: str = None, keyboard: ReplyKeyboardMarkup = None):
  update.message.reply_venue(latitude=lat, longitude=lon, title=text, address=address)

# called when user clicks on an inlinekeyboard button to go through the listed available parking
def changePage(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    data = context.user_data
    
    split = query.data.split(',')
    messageId, index = int(split[0]), int(split[1])
  
    
    # TODO: add fallback if pagination not found in data
    pagination = data.get(messageId)
    
      
    # refresh button
    text, keyboard = None, None
    if index == "refresh":
      text, keyboard = pagination.refreshAvailabilities()
    else:
      text, keyboard = pagination.getPage(index)
    
    query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

# reply the user with all the nearby carparks
def replyWithCarparkInfo(update: Update, context: CallbackContext, carparkInfo: list):
  pagination = Pagination(processCarparkInfo(carparkInfo), update.message.message_id)
  text, inlineKeyboard = pagination.getPage(0)
  context.user_data[update.message.message_id] = pagination
  return replyText(update, text, inlineKeyboard)

# ====== Telegram Message Handlers ======
# error handler
def error(update: Update, context: CallbackContext):
  logger.warning('Update "%s" caused error "%s"', update, context.error)

# start command handler
# prompts user for location, hands instructions etc.
# if successful, changes the bot to the CHOOSING state
# re-entry allowed
def start(update: Update, context: CallbackContext) -> int:
  reply_text = "Welcome to Wheretoparksg! Find available parking near you.\n\nType in your location or postal code, or <b>share your current location</b> using the button below to get started!\n\n<i>Note:\n1.You must have location services enabled for telegram in order to share your current location\n2. Parking availabilities are estimates based on data from data.gov.sg.</i>"
  
  replyText(update, reply_text, keyboard1)

  return CHOOSING

# user input handler for addresses
def inputText(update: Update, context: CallbackContext) -> int:
  # remove leading and trailing whitespace
  user_input = update.message.text.strip()
  
  if (len(user_input)) < 3:
    replyText(update, INVALID_ADDRESS)
    return

  msg = replyText(update, ADDRESS_RECEIVED)
  
  r = fetchLocationDataFromAddr(user_input)
  
  if not r or not (r.get('X') and r.get('Y')):
    # unable to fetch location dataz
    replyText(update, INVALID_ADDRESS, keyboard1)
    return CHOOSING

  addr = user_input
  if r.get('ADDRESS'):
    addr = r.get('ADDRESS')

  # inform user of search for resolved address
  # replyText(update, LOOKING_FOR_ADDRESS.format(addr=addr))
  context.bot.edit_message_text(text=LOOKING_FOR_ADDRESS.format(addr=addr), chat_id=update.message.chat_id, message_id=msg.message_id)
  
  # retrieve and display carpark information
  res = filterForCarparks(r.get('X'), r.get('Y'))
  if len(res) == 0:
    replyText(update, NO_AVAILABLE_PARKING)
    return CHOOSING
  
  replyWithCarparkInfo(update, context, res)
  
  return ConversationHandler.END


# user input handler for postal codes
# allows for whitespace in between numbers
# validates postal code format (6 numbers)
POSTAL_CODE_REGEX = r'^[0-9]{6}$'
def inputPostalCode(update: Update, context: CallbackContext) -> int:
  # remove all whitespace
  user_input = re.sub('\s', "", update.message.text)

  if not re.search(POSTAL_CODE_REGEX, user_input):
    replyText(update, INVALID_POSTAL_CODE, keyboard1)
    return CHOOSING
  
  msg = replyText(update, POSTAL_CODE_RECEIVED)
  r = fetchLocationDataFromAddr(user_input)
  
  if not r or not (r.get('X') and r.get('Y')):
    # unable to fetch location dataz
    replyText(update, INVALID_POSTAL_CODE, keyboard1)
    return CHOOSING

  addr = user_input
  if r.get('ADDRESS'):
    addr = r.get('ADDRESS')

  # inform user of search for resolved address
  # replyText(update, LOOKING_FOR_ADDRESS.format(addr=addr))
  context.bot.edit_message_text(text=LOOKING_FOR_ADDRESS.format(addr=addr), chat_id=update.message.chat_id, message_id=msg.message_id)
  
  # retrieve and display carpark information
  res = filterForCarparks(r.get('X'), r.get('Y'))
  if len(res) == 0:
    replyText(update, NO_AVAILABLE_PARKING)
    return CHOOSING
  
  replyWithCarparkInfo(update, context, res)
  return ConversationHandler.END

def inputLocation(update: Update, context: CallbackContext) -> int:
  x = update.message.location.latitude
  y = update.message.location.longitude
  
  logger.info(x)
  
  # echo the user location
  replyText(update, LOOKING_FOR_NEAR)
  
  # perform reverse geo-coding
  r = fetchLocationDataFromCoord(x, y)
  if not r or not (r.get('XCOORD') or r.get('YCOORD')):
    replyText(update, INVALID_CURRENT_LOCATION)
    return CHOOSING


  # retrieve and display carpark information
  res = filterForCarparks(r.get('XCOORD'), r.get('YCOORD'))
  if len(res) == 0:
    replyText(update, NO_AVAILABLE_PARKING)
    return CHOOSING
  
  replyWithCarparkInfo(update, context, res)
  return ConversationHandler.END

# fallback handler for unexpected user input
def fallback(update: Update, context: CallbackContext) -> int:
  replyText(update, "Send me your current location, or type in an address or postal code!")
  return CHOOSING

def startPrompt(update: Update, context: CallbackContext) -> int:
  replyText(update, "To search for carparks, use the /start command", ReplyKeyboardRemove())
  return ConversationHandler.END

# ====== Basic setup ======

def connectToDatabase() -> pymongo.collection.Collection:
  client = pymongo.MongoClient(MONGO_CONNECTION_STR.format(mongoUser=MONGO_USERNAME, mongoPwd=MONGO_PWD, databaseName=DATABASE_NAME))
  return client[DATABASE_NAME]


def setup():
  global db, logger, carparkData, TOKEN, URA_ACCESS_KEY, MY_TRANSPORT_ACCESS_KEY, ONEMAP
  # enable logging
  logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
  logger = logging.getLogger(__name__)
    
  # connect to database and retrieve collections
  db = connectToDatabase()

  if db == None:
    logger.error("Setup error: Unable to connect to database")
    return False
  logger.info("Setup: Connected to db")
  botCollection = db[BOT_COLLECTION]
  if botCollection == None:
    logger.error("Setup error: bot collection not found")
    return False
  dataCollection = db[CARPARK_COLLECTION]
  if dataCollection == None:
    logger.error("Setup error: data collection not found")
    return False
  
  # load carpark data
  carparkDataDoc = botCollection.find_one({'name': 'carparkData'})
  if not carparkDataDoc or not carparkDataDoc.get('data'):
    logger.error("Setup error: No carpark data information in db")
    return False
  carparkData = carparkDataDoc.get('data')
  
  # retrieve secrets from database
  telegramBotDoc = botCollection.find_one({'name': 'telegramBot'})
  if not telegramBotDoc or not telegramBotDoc.get('token'):
    logger.error("Setup error: No telegrambot information in db")
    return False
  TOKEN = telegramBotDoc.get('token')
  
  uraDoc = botCollection.find_one({'name': 'ura'})
  if not uraDoc or not uraDoc.get('accessKey'):
    logger.error("Setup error: No ura information in db")
    return False
  URA_ACCESS_KEY = uraDoc.get('accessKey')
  
  oneMap = botCollection.find_one({'name': 'oneMap'})
  if not oneMap or not oneMap.get('token') or not oneMap.get('exp') or not oneMap.get('email') or not oneMap.get('password'):
    logger.error("Setup error: No oneMap information in db")
    return False
  ONEMAP['email'] = oneMap.get('email')
  ONEMAP['password'] = oneMap.get('password')
  if datetime.fromtimestamp(int(oneMap.get('exp'))) < datetime.today():
    token, exp = fetchOneMapToken()
    ONEMAP['token'], ONEMAP['exp'] = token, exp
    botCollection.update_one({'_id': oneMap['_id']}, {'$set': {'token': token, 'exp': exp}} )
  else:
    ONEMAP['token'] = oneMap.get('token')
    ONEMAP['exp'] = oneMap.get('exp')
 
  myTransport = botCollection.find_one({'name': 'myTransport'})
  if not myTransport or not myTransport.get('accountKey'):
    logger.error("Setup error: No myTransport information in db")
    return False
  MY_TRANSPORT_ACCESS_KEY = myTransport.get('accountKey')
  
  logger.info("Setup: Retrieved information from db")
  # logger.info(f"token: {TOKEN}\nura access: {URA_ACCESS_KEY}\nonemap: {ONEMAP_TOKEN}\nmyTransport: {MY_TRANSPORT_ACCESS_KEY}")

  return True
    
# def addField():
#   with open('hdb-carpark-information.json', 'r') as f:
#     data = json.load(f)
#     doc = db[BOT_COLLECTION].find_one({'name': 'carparkData'})
#     db[BOT_COLLECTION].update_one({'_id': doc['_id']}, {'$set': {'data': data}})

# ====== RUN THE BOT ======
def main():
  """Setup"""
  setupSuccess = setup()
  if not setupSuccess:
    raise Exception("Error in setup, unable to proceed....")
 
  """Start the bot."""
  # Create the Updater and pass it your bot's token.
  # persistence = PicklePersistence(filename='conversationbot')
  # updater = Updater("TOKEN", persistence=persistence)
  updater = Updater(TOKEN, use_context=True)

  # Get the dispatcher to register handlers
  dispatcher = updater.dispatcher

  # # Add conversation handler
  # conv_handler = ConversationHandler(
  #     entry_points=[CommandHandler('start', start), MessageHandler(Filters.text | Filters.location | Filters.command, startPrompt)],
  #     # allow_reentry=True,
  #     states={
  #         CHOOSING: [
  #             MessageHandler(
  #               Filters.text & Filters.regex('^[\s0-9]+$') & ~(Filters.command),
  #               inputPostalCode
  #             ),
  #             MessageHandler(
  #                 Filters.text & ~(Filters.command),
  #                 inputText
  #             ),
  #             MessageHandler(Filters.location, inputLocation),
  #         ],
  #     },
  #     fallbacks=[MessageHandler(Filters.all, fallback)],
  #     name="conversation",
  #     # persistent=True,
  # )
  # dispatcher.add_handler(conv_handler)

  # use normal handlers (without conversation handler)
  dispatcher.add_handler(CommandHandler('start', start))
  dispatcher.add_handler(CallbackQueryHandler(changePage))
  dispatcher.add_handler(MessageHandler(
                Filters.text & Filters.regex('^[\s0-9]+$') & ~(Filters.command),
                inputPostalCode
              ))
  dispatcher.add_handler( MessageHandler(
                  Filters.text & ~(Filters.command),
                  inputText
              ))

  dispatcher.add_handler(MessageHandler(Filters.location, inputLocation))
  

  # show_data_handler = CommandHandler('show_data', show_data)
  # dispatcher.add_handler(show_data_handler)

  # log all errors
  # dispatcher.add_error_handler(error)

  # Start the Bot (USE THIS FOR DEPLOYMENT)
  updater.start_webhook(listen="0.0.0.0",
                        port=int(PORT),
                        url_path=TOKEN)
  updater.bot.setWebhook('https://noelle-carpark-bot.herokuapp.com/' + TOKEN)

  # # Start the Bot (USE THIS IF RUNNING LOCALLY)
  # updater.start_polling()
  
  logger.info("Bot started ♥")


  # Run the bot until you press Ctrl-C or the process receives SIGINT,
  # SIGTERM or SIGABRT. This should be used most of the time, since
  # start_polling() is non-blocking and will stop the bot gracefully.
  updater.idle()
  


if __name__ == '__main__':
    main()
