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

# CHANGE THESE GLOBAL VARIABLES
PROJECT_ID = ''
LOCATION = 'us' # Format is 'us' or 'eu'
BUCKET = ''
BUCKET_EXTRACT = ''
DATASTORE_EXTRACT = 'Extractions'


from google.cloud import documentai_v1beta3, documentai_v1beta2, language_v1, storage, datastore
from wand.image import Image as WImage
from PIL import Image, ImageDraw, ImageEnhance
import matplotlib.pyplot as plt
from skimage import data, io
from skimage.filters import threshold_otsu
import numpy as np
import pandas as pd
import os
import re

"""
Parses table from document
Eg filename = 123.gif, not with the path. Same throughout the code
"""
def parse_table(filename):

    input_uri = "gs://" +BUCKET +"/" +filename
    client = documentai_v1beta2.DocumentUnderstandingServiceClient()

    gcs_source = documentai_v1beta2.types.GcsSource(uri=input_uri)

    # mime_type can be application/pdf, image/tiff, and image/gif, or application/json
    input_config = documentai_v1beta2.types.InputConfig(
        gcs_source=gcs_source, mime_type="image/gif"
    )

    # Setting enabled=True enables table extraction
    table_extraction_params = documentai_v1beta2.types.TableExtractionParams(
        enabled=True
    )

    parent = "projects/{}/locations/us".format(PROJECT_ID)
    request = documentai_v1beta2.types.ProcessDocumentRequest(
        parent=parent,
        input_config=input_config,
        table_extraction_params=table_extraction_params,
    )

    document = client.process_document(request=request)

    print("Document processing complete.")

    # Convert text offset indexes into text snippets.
    def _get_text(el):
        response = ""
        # If a text segment spans several lines, it will
        # be stored in different text segments.
        for segment in el.text_anchor.text_segments:
            start_index = segment.start_index
            end_index = segment.end_index
            response += document.text[start_index:end_index]
        return response

    """
    Multiple tables could be detected from the document, this is to make sure you are getting the nutrition table
    Use specific keywords to identity what's usually in a nutrition table
    """
    def _detectIngredientsTbl(table):

        keywords = ["energy", "carbohydrate", "protein", "fat"]
        match = 0

        for row_num, row in enumerate(table.body_rows):
            i = 0
            for cell in row.cells:
                if i == 0:
                    cell = _get_text(cell.layout).rstrip().lstrip().lower()
                    for key in keywords:
                        if key in cell:
                            match += 1
                i += 1

        return match > 2

    """This is the return variable
       str[0] is the nutrition table in html
       str[1] is 'Made in Australia ...'
    """
    str = ["",""]
    for page in document.pages:
        # print("Page number: {}".format(page.page_number))

        for table_num, table in enumerate(page.tables):
            # print("Table {}: ".format(table_num))

            for row_num, row in enumerate(table.header_rows):
                cells = " ".join([_get_text(cell.layout) for cell in row.cells]).lower()
                # print("Header Row {}: {}".format(row_num, cells))
                if _detectIngredientsTbl(table):

                        str[0] += "<thead><tr><th colspan='42'><input type='hidden' id='productLinked' file='"+filename +"'></input>Nutrition Information</th></tr></thead>"

                        tmp = "<tr>"
                        discard = False

                        # find repeated header - discard this since a proper one has been created above
                        if "nutrition" not in cells or "information" not in cells:

                            for cell in row.cells:
                                cell = _get_text(cell.layout).rstrip().lstrip()
                                tmp += "<td>" +cell +"</td>"
                        else:
                            discard = True

                        if not discard:
                            tmp += "</tr>"
                        else:
                            tmp = ""

                        str[0] += tmp

                        # iterate each row in the nutrition table
                        for row_num, row in enumerate(table.body_rows):
                            cells = " ".join([_get_text(cell.layout) for cell in row.cells]).lower()
                            tmp = "<tr>"
                            idx = 0
                            process = False
                            discard = False

                            # bypass the header which is usually entitled nutrition information, or similar
                            if "nutrition" not in cells or "information" not in cells:

                                for cell in row.cells:
                                    cell = _get_text(cell.layout).rstrip().lstrip()
                                    if idx == 0:
                                        process = not cell.endswith("g)") and not cell.endswith("J)")
                                        idx += 1
                                    else:
                                        cell = preprocess(cell, process)
                                        
                                    # print (cell)
                                    tmp += "<td>" +cell +"</td>"
                                
                            else:
                                discard = True

                            if not discard:
                                tmp += "</tr>"
                            else:
                                tmp = ""

                            str[0] += tmp

    # str[1] = parse_paragraph(filename)
    str[1] = query_datastore(filename)

    return str

"""
 Calling Document AI API to extract the paragraphs in the document, using generic OCR processor
"""
def parse_paragraph(filename):

    """Parse a form"""

    input_uri = "gs://" +BUCKET_EXTRACT +"/" +filename

    # Check if file exists
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_EXTRACT)
    if not storage.Blob(bucket=bucket, name=filename).exists(storage_client):
        return ""

    client = documentai_v1beta2.DocumentUnderstandingServiceClient()

    # Extract text
    gcs_source = documentai_v1beta2.types.GcsSource(uri=input_uri)
    # mime_type can be application/pdf, image/tiff, and image/gif, or application/json
    input_config = documentai_v1beta2.types.InputConfig(
        gcs_source=gcs_source, mime_type="image/gif"
    )

    parent = "projects/{}/locations/us".format(PROJECT_ID)
    request = documentai_v1beta2.types.ProcessDocumentRequest(
        parent=parent,
        input_config=input_config,
    )

    document = client.process_document(request=request)

    print("Document extract processing complete.")
       
    def _get_text_ocr(doc_element:dict, document:dict):
        """
        Document AI identifies form fields by their offsets
        in document text. This function converts offsets
        to text snippets.
        """
        response = ""
        # If a text segment spans several lines, it will
        # be stored in different text segments.
        for segment in doc_element.text_anchor.text_segments:
            start_index = (
                int(segment.start_index)
                if segment in doc_element.text_anchor.text_segments
                else 0
            )
            end_index = int(segment.end_index)
            response += document.text[start_index:end_index]
        return response

    # Read the text recognition output from the processor
    # print("The document contains the following paragraphs:")
    str = ""
    for page in document.pages:
        paragraphs = page.paragraphs
        for paragraph in paragraphs:
            paragraph_text = _get_text_ocr(paragraph.layout, document)
            if "australia" in paragraph_text.lower():
                str = paragraph_text
                break

            # print(f"Paragraph text: {paragraph_text}")

    return str


"""
 Assuming a backend Cloud Function that extracts the paragraphs upon trigger of a new file being deposited into a bucket
 This new file, is the 'Made In Australia' bounding box extracted from another Cloud Function
"""
def query_datastore(filename):

    # Instantiates a client
    client = datastore.Client()
    # The Cloud Datastore key for the new entity
    query = client.query(kind=DATASTORE_EXTRACT)
    key = client.key(DATASTORE_EXTRACT, filename)
    query.key_filter(key,'=')
    # Prepares the new entity
    results = list(query.fetch())
    str = ""
    for entity in results:
        print("Document extract processing complete.")
        str = entity["Text"]

    return str


"""
 Some of the text extracted contains erroneously recognized character such as 'g' being mistaken as '9' or '0' by the API
 Only process if the header doesn't contain (ml), (kJ) which means the table content should be just number
 Otherwise, table content should end with metrics, such as 2mg or 10kJ. In this case a 9 at end most likely means the character was recognized wrongly
"""
def preprocess(str, process):

    result = str

    if process:
        try:
            float(result)
            result = result[:-1] +"g" if result.endswith("9") or result.endswith("0") else result
        except ValueError:
            # should be just a number
            result = result.replace("o","0").replace("O","0")
    else:
        # should be just a number
        result = result.replace("o","0").replace("O","0")

    return result


"""
 Was playing around with NLP API but wasn't useful
 Analyzing Entities in a String
    Args:
      text_content The text content to analyze
"""
def sample_analyze_entities(text_content):

    client = language_v1.LanguageServiceClient()

    # text_content = 'California is a state.'

    # Available types: PLAIN_TEXT, HTML
    type_ = language_v1.Document.Type.PLAIN_TEXT

    # Optional. If not specified, the language is automatically detected.
    # For list of supported languages:
    # https://cloud.google.com/natural-language/docs/languages
    language = "en"
    document = {"content": text_content, "type_": type_, "language": language}

    # Available values: NONE, UTF8, UTF16, UTF32
    encoding_type = language_v1.EncodingType.UTF8

    response = client.analyze_entities(request = {'document': document, 'encoding_type': encoding_type})

    # Loop through entitites returned from the API
    for entity in response.entities:
        print(u"Representative name for the entity: {}".format(entity.name))

        # Get entity type, e.g. PERSON, LOCATION, ADDRESS, NUMBER, et al
        print(u"Entity type: {}".format(language_v1.Entity.Type(entity.type_).name))

        # Get the salience score associated with the entity in the [0, 1.0] range
        print(u"Salience score: {}".format(entity.salience))

        # Loop over the metadata associated with entity. For many known entities,
        # the metadata is a Wikipedia URL (wikipedia_url) and Knowledge Graph MID (mid).
        # Some entity types may have additional metadata, e.g. ADDRESS entities
        # may have metadata for the address street_name, postal_code, et al.
        for metadata_name, metadata_value in entity.metadata.items():
            print(u"{}: {}".format(metadata_name, metadata_value))

        # Loop over the mentions of this entity in the input document.
        # The API currently supports proper noun mentions.
        for mention in entity.mentions:
            print(u"Mention text: {}".format(mention.text.content))

            # Get the mention type, e.g. PROPER for proper noun
            print(
                u"Mention type: {}".format(language_v1.EntityMention.Type(mention.type_).name)
            )

    # Get the language of the text, which will be the same as
    # the language specified in the request or, if not specified,
    # the automatically-detected language.
    print(u"Language of the text: {}".format(response.language))




