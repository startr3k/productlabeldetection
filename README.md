# Product Label Detection

This code demonstrates Google Cloud Document AI in detecting nutrition information and % of Made in Australia ingredients in product labels

It is based on Flask, and the following Google Cloud serverless components

* Document AI
* AutoML Vision Object Detection
* Cloud Storage
* Cloud Functions
* Cloud Datastore
* Cloud Build
* Container Registry
* Cloud Run
* Firebase

## Configuring

The environment variables in the following files need to be modified based on your own Google Cloud environment :

* main.py (Flask)
* DocAI.py

The variables to modify are :

  * PROJECT_ID - Your Google Cloud project id
  * BUCKET_LABEL - This is the storage bucket that contains all your product label images
  * BUCKET_EXTRACT - This is the storage bucket that contains the 'Made In Australia' section extracted out of the product labels with AutoML Vision
  * DATASTORE_EXTRACT - Name of the kind created in Datastore for storing the text extracted from the 'Made In Australia' section
  * DATASTORE_USER - Name of the kind created in Datastore for storing users (authentication is done by Firebase)


## Bootstrapping your environment in Google Cloud

1. Make sure you have installed Google Cloud SDK (https://cloud.google.com/sdk/docs/install)

2. Create a service account and save the key as key.json under the productlabeldetection folder.

3. Enable the following APIs

  * Document AI
  * Vertex AI
  * Cloud Storage
  * Cloud Functions
  * Cloud Datastore
  * Cloud Build
  * Container Registry
  * Cloud Run
  * Identity Platform

4. Run the following commands to bootstrap the environment (regions should be preferably us-central1) :

    gsutil mb -p <PROJECT_ID> -c STANDARD -l us-central1 -b on gs://<BUCKET_LABEL>
    
    gsutil mb -p <PROJECT_ID> -c STANDARD -l us-central1 -b on gs://<BUCKET_EXTRACT>
    
    gsutil iam ch allUsers:objectViewer gs://<BUCKET_LABEL>
    
    gsutil iam ch allUsers:objectViewer gs://<BUCKET_EXTRACT>
    
    gsutil iam ch serviceAccount:<COMPUTE_ENGINE_DEFAULT_SERVICE_ACCOUNT>:objectCreator gs://<BUCKET_EXTRACT>
  

5a. Create entities in Datastore under Kind = DATASTORE_USER, ID = Numeric ID (auto generated). Add property, where 

   name = **Email** and value = <Gmail/Google email addresses> (Google IdP) or <any email address>
   
5b. If Google IdP is not required, create the user in Identity Platform with email and password
 
  (For Google IdP, by default auto sign up is enabled, so the user will be added automatically)

## Train AutoML Vision Object Detection

1. Unzip the sample images from samples.zip

2. Create a dataset in AutoML Vision Object Detection and upload these images

3. Label the 'Made In Australia' bounding boxes in each image

4. Train and deploy the model (choose the high accuracy option)

5. Click on the Python symbol and obtain the Model ID from the sample code


## Set Up Cloud Functions

Run the following, replacing MODEL_ID with value obtained above :

    gcloud functions deploy extractImgMadeInAustralia --runtime python39 --trigger-resource <BUCKET_LABEL> --trigger-event google.storage.object.finalize --memory=1024MB --set-env-vars PROJECT_ID=<PROJECT_ID>,MODEL_ID=<MODEL_ID>,BUCKET_EXTRACT=<BUCKET_EXTRACT> --service-account=<COMPUTE_ENGINE_DEFAULT_SERVICE_ACCOUNT>

    gcloud functions deploy extractTextMadeInAustralia --runtime python39 --trigger-resource <BUCKET_EXTRACT> --trigger-event google.storage.object.finalize --memory=1024MB --set-env-vars PROJECT_ID=<PROJECT_ID>,DATASTORE_EXTRACT=<DATASTORE_EXTRACT> --service-account=<COMPUTE_ENGINE_DEFAULT_SERVICE_ACCOUNT>


## Load Images

1. After the Cloud Functions are deployed, run the following to upload the unzipped images :

    gsutil cp *.jpg gs://<BUCKET_LABEL>

2. Take note of the new files extracted in gs://<BUCKET_EXTRACT> and the new Entities created in Datastore

## Buid the application on Cloud Build

    gcloud builds submit --tag gcr.io/<PROJECT_ID>/productlabeldetection


## Deploy application on Cloud Run

    gcloud run deploy productlabeldetection --image gcr.io/<PROJECT_ID>/productlabeldetection --platform managed --region us-central1
    
## Accessing the application

    Go to Cloud Run, and access the webpage with the URL given


***(By default Cloud Run uses the default compute engine service account. If a separate service account is required, just change the commands above accordingly)***

# Architecture Diagram
 
 ![alt text](https://github.com/startr3k/productlabeldetection/blob/main/PLD.drawio.png?raw=true)
