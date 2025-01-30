import uuid
import boto3
import io
from django.conf import settings


def s3_client():
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    return s3_client


def upload_to_s3(image_content):
    s3 = s3_client()
    unique_identifier = str(uuid.uuid4())
    s3_object_key = f'profile-images/{unique_identifier}.jpg'
    s3_bucket = settings.AWS_STORAGE_BUCKET_NAME
    s3.upload_fileobj(io.BytesIO(image_content), s3_bucket, s3_object_key)
    s3_url = f'https://{s3_bucket}.s3.amazonaws.com/{s3_object_key}'
    return s3_url


def delete_from_s3(s3_object_key):
    s3 = s3_client()
    print(s3_object_key)
    s3_bucket = settings.AWS_STORAGE_BUCKET_NAME
    try:
        s3.delete_object(Bucket=s3_bucket, Key=s3_object_key)
        return True
    except:
        return False
    
def pdf_to_s3_url(file_content, file_name):
    s3 = s3_client()
    s3_bucket = settings.AWS_STORAGE_BUCKET_NAME
    unique_identifier = str(uuid.uuid4())
    s3_object_key = f'reports/{unique_identifier}_{file_name}'
    s3.upload_fileobj(io.BytesIO(file_content), s3_bucket, s3_object_key)
    s3_url = f'https://{s3_bucket}.s3.amazonaws.com/{s3_object_key}'
    return s3_url