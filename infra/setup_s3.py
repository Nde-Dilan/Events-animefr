# setup_s3.py : Upload d'un épisode → S3 notifie Lambda automatiquement → pipeline démarre


import boto3
import json

s3 = boto3.client('s3')
REGION = 'eu-west-1'

BUCKETS = [
    'animefr-episodes',   # vidéos source (MP4)
    'animefr-audio',      # audio extrait (MP3/WAV)
    'animefr-outputs',    # sous-titres .SRT + audio doublé
]

def create_buckets():
    for name in BUCKETS:
        try:
            s3.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={'LocationConstraint': REGION}
            )
            print(f"  Bucket créé : {name}")
        except s3.exceptions.BucketAlreadyOwnedByYou:
            print(f"  Bucket existe déjà : {name}")

    # Bloquer l'accès public (bonne pratique)
    for name in BUCKETS:
        s3.put_public_access_block(
            Bucket=name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True,
            }
        )
    print("  Accès public bloqué sur tous les buckets")

if __name__ == '__main__':
    create_buckets()