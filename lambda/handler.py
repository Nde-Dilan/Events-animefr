# handler.py

import json
import boto3
import os
import urllib.parse

# Ces imports viennent du layer Lambda (on les configure après)
from pipeline.transcribe import start_transcription
from pipeline.translate import translate_transcript
from pipeline.subtitle import generate_srt
from pipeline.tts import synthesize_voice
from pipeline.db import save_job_status

s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Déclenché automatiquement par S3 à chaque upload dans animefr-episodes/
    """
    # Récupérer les infos du fichier uploadé
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key    = urllib.parse.unquote_plus(record['s3']['object']['key'])

    print(f"Nouvel épisode détecté : s3://{bucket}/{key}")

    # Extraire le nom de l'épisode (ex: "one-piece-ep1045")
    episode_id = key.replace('.mp4', '').replace('/', '-')

    # Sauvegarder le statut initial dans DynamoDB
    save_job_status(episode_id, status='STARTED', source_key=key)

    try:
        # ÉTAPE A — Transcription audio → texte
        print(f"[1/4] Transcription en cours...")
        transcript = start_transcription(
            bucket=bucket,
            key=key,
            episode_id=episode_id,
            source_lang='en-US'   # ou 'ja-JP' pour du japonais
        )
        save_job_status(episode_id, status='TRANSCRIBED')

        # ÉTAPE B — Traduction EN/JP → FR
        print(f"[2/4] Traduction en cours...")
        translated_segments = translate_transcript(
            transcript=transcript,
            source_lang='en',
            target_lang='fr'
        )
        save_job_status(episode_id, status='TRANSLATED')

        # ÉTAPE C — Génération du fichier .SRT
        print(f"[3/4] Génération des sous-titres...")
        srt_key = generate_srt(
            segments=translated_segments,
            episode_id=episode_id,
            output_bucket='animefr-outputs'
        )
        save_job_status(episode_id, status='SUBTITLED', srt_key=srt_key)

        # ÉTAPE D — Doublage avec Amazon Polly
        print(f"[4/4] Synthèse vocale (doublage FR)...")
        audio_key = synthesize_voice(
            segments=translated_segments,
            episode_id=episode_id,
            output_bucket='animefr-outputs'
        )
        save_job_status(episode_id, status='COMPLETED',
                        srt_key=srt_key, audio_key=audio_key)

        print(f"Pipeline terminée pour {episode_id}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'episode_id': episode_id,
                'srt': srt_key,
                'audio': audio_key
            })
        }

    except Exception as e:
        print(f"ERREUR pipeline : {str(e)}")
        save_job_status(episode_id, status='FAILED', error=str(e))
        raise