# demo/test_etape3.py
import sys
sys.path.insert(0, '.')

from pipeline.transcribe import start_transcription
from pipeline.translate  import translate_transcript
from pipeline.subtitle   import generate_srt

# 1. Transcription d'un clip audio de test
#    (uploade d'abord un .mp3 court dans animefr-episodes/)
transcript = start_transcription(
    bucket='animefr-episodes',
    key='test_clip.mp3',
    episode_id='test-ep001',
    source_lang='ja-JP'
)

print("\n--- Transcription ---")
for seg in transcript[:3]:  # Affiche les 3 premiers segments
    print(f"  [{seg['start']}s → {seg['end']}s] {seg['text']}")

# 2. Traduction
translated = translate_transcript(transcript, source_lang='ja-JP', target_lang='fr')

print("\n--- Traduction ---")
for seg in translated[:3]:
    print(f"  [{seg['start']}s → {seg['end']}s]")
    print(f"    JP : {seg['original']}")
    print(f"    FR : {seg['text']}")

# 3. Génération du .SRT
srt_key = generate_srt(translated, 'test-ep001', 'animefr-outputs')
print(f"\n--- SRT généré : s3://animefr-outputs/{srt_key}")

# 4. Télécharger et afficher le SRT
import boto3
obj = boto3.client('s3').get_object(Bucket='animefr-outputs', Key=srt_key)
print("\n--- Contenu SRT (extrait) ---")
print(obj['Body'].read().decode('utf-8')[:500])