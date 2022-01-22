import flask
from flask_caching import Cache

import firebase_admin
import firebase_admin.credentials
from firebase_admin import firestore

import json
import time
import requests
from datetime import datetime, timedelta

# Initialize firestore
cred = firebase_admin.credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
firestore_db = firestore.client()

# Polygon API key
apiKey = "0ZaaYzNYsgi2Mv24J7EEwIAdJhrjuiGJ"

# Flask
app = flask.Flask(__name__)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})

# Gets date from datetime
def dateFromDatetime(dt):
	return dt.isoformat().split('T')[0]

# Gets stock prices
def getStockPrices(ticker, attemptNum):
	today = datetime.now()
	beforeToday = today - timedelta(days=4)
	resp = requests.get("https://api.polygon.io/v2/aggs/ticker/%s/range/1/hour/%s/%s?adjusted=true&sort=desc&limit=1000&apiKey=%s" % (ticker, dateFromDatetime(beforeToday), dateFromDatetime(today), apiKey))
	try:
		results = json.loads(resp.content)["results"]
		newestValue = results[0]["v"]
		currentDay = datetime.fromtimestamp(results[0]["t"]/1000).day
		previousValue = None
		for entry in results:
			if datetime.fromtimestamp(entry["t"]/1000).day != currentDay:
				previousValue = entry["v"]
				break
		if previousValue is None:
			raise Exception("Previous value doesn't exist!?")
		return (newestValue, previousValue)
	except KeyError:
		time.sleep(10)
		if attemptNum > 10:
			raise Exception("Some type of error is consistently happening")
		return getStockPrices(ticker, attemptNum+1)

# Cached ticker metadata (changes at most once per hour)
@app.route("/tickerMetadata")
@cache.cached(timeout=3600, query_string=True)
def showTickerMetadata():
	ticker = flask.request.args['ticker']
	if not ticker.isupper() or not ticker.isalpha():
		return '{"result":"error","message":"ticker invalid"}'
	# Get rating from firebase.
	totalRating = 0
	totalReviews = 0
	for review in firestore_db.collection('User/Ticker/%s' % ticker).get():
		totalRating += review.get('rating')
		totalReviews += 1
	if totalReviews > 0:
		averageRating = totalRating / totalReviews
	else:
		averageRating = 0.0
	# Get stock price compared to yesterday's close
	newestValue, previousValue = getStockPrices(ticker, 0)
	return json.dumps({"rating": averageRating, "newestValue": newestValue, "previousValue": previousValue})

if __name__ == "__main__":
	app.run()
