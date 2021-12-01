import os
import io
from PIL import Image

from google.cloud import automl
from google.cloud import storage

def extractImgMadeInAustralia(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    file = event
    print(f"Processing file: {file['name']}.")
    
    prediction_client = automl.PredictionServiceClient()

    # Get the full path of the model.
    model_full_id = automl.AutoMlClient.model_path(os.environ['PROJECT_ID'], "us-central1", os.environ['MODEL_ID'])

    client = storage.Client()
    source_bucket = client.get_bucket(file['bucket'])
    source_blob = source_bucket.get_blob(file['name'])
    #content = np.asarray(bytearray(source_blob.download_as_string()), dtype="uint8")
    #content= cv2.imdecode(content, cv2.IMREAD_UNCHANGED)
    image_bytes = source_blob.download_as_bytes()

    img = Image.open(io.BytesIO(image_bytes))

    image = automl.Image(image_bytes=image_bytes)
    payload = automl.ExamplePayload(image=image)

    # params is additional domain-specific parameters.
    # score_threshold is used to filter the result
    # https://cloud.google.com/automl/docs/reference/rpc/google.cloud.automl.v1#predictrequest
    params = {"score_threshold": "0.5"}

    request = automl.PredictRequest(name=model_full_id, payload=payload, params=params)

    response = prediction_client.predict(request=request)

    x1 = 0
    y1 = 0
    x2 = 0
    y2 = 0

    for result in response.payload:
        # print("Predicted class name: {}".format(result.display_name))
        # print("Predicted class score: {}".format(result.image_object_detection.score))
        bounding_box = result.image_object_detection.bounding_box
        # print("Normalized Vertices:")
        i = 0
        for vertex in bounding_box.normalized_vertices:
            # print("\tX: {}, Y: {}".format(vertex.x, vertex.y))
            if i == 0:
                x1 = vertex.x
                y1 = vertex.y
            elif i == 1:
                x2 = vertex.x
                y2 = vertex.y

            i += 1

    w, h = img.size
    x1 = int(x1 * w)
    y1 = int(y1 * h)

    x2 = int(x2 * w)
    y2 = int(y2 * h)

    img_crop = img.crop((x1, y1, x2, y2))

    img_byte_array = io.BytesIO()
    img_crop.save(img_byte_array, format="GIF")
    img_byte_array.seek(0)

    destination_bucket = client.get_bucket(os.environ['BUCKET_EXTRACT'])
    destination_blob = destination_bucket.blob(file['name'])
    destination_blob.upload_from_string(img_byte_array.getvalue(), content_type='image/gif')

    print("Image extracted.")
