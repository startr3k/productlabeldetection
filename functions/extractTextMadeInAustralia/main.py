import os
import io
from google.cloud import storage, documentai_v1beta2, datastore

def extractTextMadeInAustralia(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    file = event
    print(f"Processing file: {file['name']}.")

    """Parse a form"""

    # Get env variables
    BUCKET_EXTRACT = file['bucket']
    PROJECT_ID = os.environ['PROJECT_ID']
    DATASTORE_EXTRACT = os.environ['DATASTORE_EXTRACT']
    filename = file['name']
    
    input_uri = "gs://" +BUCKET_EXTRACT +"/" +filename

    client = documentai_v1beta2.DocumentUnderstandingServiceClient()

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

    # Instantiates a client
    client = datastore.Client()
    # The Cloud Datastore key for the new entity

    complete_key = client.key(DATASTORE_EXTRACT, filename)

    task = datastore.Entity(key=complete_key)

    task.update(
        {
            "Text": str,
        }
    )

    client.put(task)

    print(f"Inserted: {str}")
    
    return str
