# WhereToParkSG
A telegram bot that helps search for nearby parking in Singapore based on your current location, an address or a postal code

## Maintenance Instructions
### Deployment
Take note of the following environment variables the application relies on.
Should the deployment platform be changed, these environment variables should be set in a similar manner. <br>

*In Heroku, these can be configured under `Settings > Config Vars`*

#### Environment Variables
|Variables|Remarks|
| ------ |-------|
|MONGO_USERNAME|Username for MongoDB|
|MONGO_PWD|Password for MongoDB|
|DATABASE_NAME|Name of the database (Wheretoparksg)|
|BOT_COLLECTION|Name of the collection (bot)|
|CARPARK_RANGE|The maximum straight line distance from the current location in order to consider a carpark|
|CARPARK_LIMIT|The maximum number of carparks to display|
|DEV_ENV|In your deployment environment, set this to PROD|

### Modifying Carpark Data (using `script.py`)
*Note: You need to have Python 3 and above.* <br><br>
This script searches for the document in the mongo collection with `name = 'carparkData'` and replaces the value of `data` with the data in your `carparks.json`.
#### Instructions
1. In the same folder as `script.py`, place your json file containing **all** needed carpark data. The file should be called `carparks.json`.
2. Ensure that the variables (`MONGO_CONNECTION_STR`, `MONGO_USERNAME`, `MONGO_PWD`, `DATABASE_NAME`, `BOT_COLLECTION`) are filled up correctly. These can be taken from your application's environment variables.
**You should keep your passwords safe. Never share them with anyone!**
3. To install the required dependencies, run `pip install pymongo` (if on Mac or not using a venv, you run `pip3 install pymongo`). You may skip this step if you have already installed your dependencies.
4. Run `python script.py` to run the script. (if on Mac or not using a venv, run `python3 script.py`)



