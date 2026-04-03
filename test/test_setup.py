# test_setup.py — small script to test connection with your configure aws account,if you get region error just specify region or use this : export AWS_DEFAULT_REGION=eu-west-1
import boto3

services = {
    's3':         boto3.client('s3'),
    'transcribe': boto3.client('transcribe'),
    'translate':  boto3.client('translate'),
    'polly':      boto3.client('polly'),
    'dynamodb':   boto3.client('dynamodb'),
}

for name, client in services.items():
    try:
        if name == 's3':         client.list_buckets()
        if name == 'transcribe': client.list_transcription_jobs(Status='COMPLETED')
        if name == 'translate':  client.list_terminologies()
        if name == 'polly':      client.describe_voices(LanguageCode='fr-FR')
        if name == 'dynamodb':   client.list_tables()
        print(f"  {name} — OK")
    except Exception as e:
        print(f"  {name} — ERREUR : {e}")