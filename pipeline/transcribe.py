# transcribe.py

# Chaque segment garde son timestamp → synchronisation parfaite avec la vidéo

import boto3
import time
import json

transcribe = boto3.client('transcribe')
s3         = boto3.client('s3')

def start_transcription(bucket: str, key: str, episode_id: str,
                         source_lang: str = 'en-US') -> list[dict]:
    """
    Soumet un job Transcribe et retourne les segments avec timestamps.

    Retourne une liste de segments :
    [
      {'start': 1.23, 'end': 3.45, 'text': 'Welcome to the Hidden Leaf Village.'},
      ...
    ]
    """
    job_name   = f"animefr-{episode_id}-{int(time.time())}"
    media_uri  = f"s3://{bucket}/{key}"

    print(f"  Soumission du job Transcribe : {job_name}")

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': media_uri},
        MediaFormat=_detect_format(key),
        LanguageCode=source_lang,
        OutputBucketName=bucket,
        OutputKey=f"transcripts/{episode_id}.json",
        Settings={
            'ShowSpeakerLabels': False,
            'ShowAlternatives':  False,
        }
    )

    # Polling — on attend la fin du job (max 30 min)
    result = _wait_for_job(job_name, bucket, f"transcripts/{episode_id}.json")
    return _parse_transcript(result)


def _detect_format(key: str) -> str:
    ext = key.rsplit('.', 1)[-1].lower()
    return {'mp4': 'mp4', 'mp3': 'mp3', 'wav': 'wav',
            'flac': 'flac', 'm4a': 'mp4'}.get(ext, 'mp4')


def _wait_for_job(
    job_name: str,
    output_bucket: str,
    output_key: str,
    poll_interval: int = 10
) -> dict:
    """Attend la fin du job en interrogeant Transcribe toutes les 10s."""
    while True:
        response = transcribe.get_transcription_job(
            TranscriptionJobName=job_name
        )
        status = response['TranscriptionJob']['TranscriptionJobStatus']

        if status == 'COMPLETED':
            print(f"  Transcription terminée.")
            # Récupérer le JSON depuis S3 (bucket de sortie du job)
            try:
                return _fetch_transcript_from_s3(output_bucket, output_key)
            except Exception as s3_error:
                print(f"  Lecture S3 directe impossible ({s3_error}), fallback HTTPS...")

            # Fallback: URL HTTPS renvoyée par Transcribe
            uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
            return _fetch_transcript_json(uri)

        elif status == 'FAILED':
            reason = response['TranscriptionJob'].get('FailureReason', 'Inconnue')
            raise RuntimeError(f"Transcription échouée : {reason}")

        else:
            print(f"  Statut : {status} — attente {poll_interval}s...")
            time.sleep(poll_interval)


def _fetch_transcript_json(uri: str) -> dict:
    """Télécharge le JSON de résultat depuis S3 ou via HTTPS."""
    import urllib.request
    with urllib.request.urlopen(uri) as response:
        return json.loads(response.read())


def _fetch_transcript_from_s3(bucket: str, key: str) -> dict:
    """Télécharge le JSON de résultat directement depuis S3."""
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj['Body'].read().decode('utf-8')
    return json.loads(body)


def _parse_transcript(raw: dict) -> list[dict]:
    """
    Convertit le JSON Transcribe en liste de segments lisibles.
    Regroupe les mots en phrases (~10 mots max ou pause > 1.5s).
    """
    items = raw['results']['items']
    segments = []
    current_words   = []
    current_start   = None
    current_end     = None

    for item in items:
        if item['type'] == 'punctuation':
            if current_words:
                current_words[-1]['text'] += item['alternatives'][0]['content']
            continue

        word  = item['alternatives'][0]['content']
        start = float(item['start_time'])
        end   = float(item['end_time'])

        # Nouvelle phrase si : pause > 1.5s OU > 10 mots
        if current_start is not None:
            gap = start - current_end
            if gap > 1.5 or len(current_words) >= 10:
                segments.append(_make_segment(current_words,
                                              current_start, current_end))
                current_words = []
                current_start = None

        if current_start is None:
            current_start = start

        current_words.append({'text': word})
        current_end = end

    # Dernier segment
    if current_words:
        segments.append(_make_segment(current_words, current_start, current_end))

    print(f"  {len(segments)} segments extraits.")
    return segments


def _make_segment(words: list, start: float, end: float) -> dict:
    return {
        'start': round(start, 3),
        'end':   round(end, 3),
        'text':  ' '.join(w['text'] for w in words)
    }