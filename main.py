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
import os
import signal
import sys
from DocAI import parse_table
from types import FrameType
from flask import Flask, g, render_template, request, Response, jsonify
from markupsafe import Markup
import middleware
from middleware import jwt_authenticated, logger, getDisplayName
from google.cloud import datastore, storage

# Configuration is read from the environment so deployments can supply their own
# values without editing source.
BUCKET_LABEL = os.environ.get("BUCKET_LABEL", "")
DATASTORE_USER = os.environ.get("DATASTORE_USER", "Users")


# Credentials are resolved by the Google client libraries through Application
# Default Credentials. GOOGLE_APPLICATION_CREDENTIALS must be set in the process
# environment for a key file to be used; setting it in the Flask config (as this
# module previously did) has no effect on the clients.
app = Flask(__name__, static_folder="static", static_url_path="")

productlist = []


def storage_base() -> str:
    """Public base URL for product images, derived from the configured bucket."""
    if not BUCKET_LABEL:
        return ""
    return f"https://storage.googleapis.com/{BUCKET_LABEL}"


def render_products(**context) -> str:
    """Render the results page with the shared template context."""
    return render_template(
        "productlabel.html",
        user=getDisplayName(),
        products=productlist,
        firstProduct=productlist[0] if productlist else "",
        storage_base=storage_base(),
        **context,
    )

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
    blobs = storage_client.list_blobs(BUCKET_LABEL)
    global productlist
    productlist = []

    for blob in blobs:
        if blob.content_type == 'image/gif':
            productlist.append(blob.name)

    return render_products()

"""
 Page that calls the DocAI.py function parse_table
"""
@app.route("/package", methods=["POST"])
@jwt_authenticated
def hello_world() -> str:
    filename = request.form["img"]
    #filename = filename.split(".")[0] + ".tiff"
    extracted_text = parse_table(filename[1:])
    print(extracted_text, file=sys.stderr)

    # 'ingredients' is HTML assembled by DocAI from escaped cell values, so it
    # is safe to mark up. 'others' is plain OCR text and stays escaped by Jinja.
    return render_products(
        ingredients=Markup(extracted_text[0]),
        others=extracted_text[1],
    )

"""
 Page that ensure the user is a legit one, by verifying against Datastore
 To give new user access through Google account, just add them as a new entity in Datastore
"""
@app.route("/verify", methods=["POST"])
@jwt_authenticated
def verify_users() -> str:
    # The email comes from the verified Firebase token, not from client input,
    # so a caller cannot probe whether an arbitrary address is registered.
    email = g.email
    if not email:
        return "0"

    # Instantiates a client
    client = datastore.Client()
    # The Cloud Datastore key for the new entity
    query = client.query(kind=DATASTORE_USER)
    query.add_filter("Email", "=", email)
    # Prepares the new entity
    results = list(query.fetch())

    return "1" if results else "0"

if __name__ == "__main__":
    # handles Ctrl-C locally
    app.run(debug=True,host='0.0.0.0',port=int(os.environ.get('PORT', 8080)))
