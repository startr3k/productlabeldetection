"""
 Copyright 2021 Google LLC
 Licensed under the Apache License, Version 2.0 (the `License`);
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
 
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an `AS IS` BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

import datetime
import signal
import sys
from DocAI import parse_table
from types import FrameType
from flask import Flask, render_template, request, Response, Markup, jsonify
import middleware
from middleware import jwt_authenticated, logger, getDisplayName
from google.cloud import datastore, storage

# CHANGE THESE GLOBAL VARIABLES
BUCKET_LABEL = ''
DATASTORE_USER = 'Users'


app = Flask(__name__, static_folder="static", static_url_path="")
app.config['GOOGLE_APPLICATION_CREDENTIALS']='key.json'

productlist = []

"""
 Main page
"""
@app.route("/", methods=["GET"])
def index() -> str:
    return render_template("index.html")

"""
 Page that gets the name of the images from Cloud Storage bucket to display
"""
@app.route("/package", methods=["GET"])
@jwt_authenticated
def view_package() -> str:

    # List images in Cloud Storage
    storage_client = storage.Client()
    bucket_name = BUCKET_LABEL
    blobs = storage_client.list_blobs(bucket_name)
    global productlist
    productlist = []
    firstprod = ""

    for blob in blobs:
        if blob.content_type == 'image/gif':
            productlist.append(blob.name)

    if productlist:
        firstprod = productlist[0]

    return render_template("productlabel.html",user=Markup(getDisplayName()),products=productlist,firstProduct=firstprod)

"""
 Page that calls the DocAI.py function parse_table
"""
@app.route("/package", methods=["POST"])
@jwt_authenticated
def hello_world() -> str:
    firstprod = ""
    filename = request.form["img"]
    #filename = filename.split(".")[0] + ".tiff"
    extracted_text = parse_table(filename[1:])
    print(extracted_text, file=sys.stderr)
    
    if productlist:
        firstprod = productlist[0]

    return render_template("productlabel.html", ingredients=Markup(extracted_text[0]),others=Markup(extracted_text[1]),user=request.form["user"],products=productlist,firstProduct=firstprod)

"""
 Page that ensure the user is a legit one, by verifying against Datastore
 To give new user access through Google account, just add them as a new entity in Datastore
"""
@app.route("/verify", methods=["POST"])
def verify_users() -> str:
    email = request.form["email"]
    # Instantiates a client
    client = datastore.Client()
    # The Cloud Datastore key for the new entity
    query = client.query(kind=DATASTORE_USER)
    query.add_filter("Email", "=", email)
    # Prepares the new entity
    results = list(query.fetch())
    i = 0
    if results:
        for entity in results:
            i += 1

    return "1" if i>0 else "0"

if __name__ == "__main__":
    # handles Ctrl-C locally
    app.run(debug=True,host='0.0.0.0',port=int(os.environ.get('PORT', 8080)))
