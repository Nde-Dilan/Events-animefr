# tts.py

import boto3
import io
import time

s3    = boto3.client('s3')
polly = boto3.client('polly')

# Voix neurales françaises disponibles dans Polly
VOICES = {
    'female': 'Lea',      # Voix féminine naturelle — recommandée
    'male':   'Mathieu',  # Voix masculine
}

def synthesize_voice(segments: list[dict], episode_id: str,
                     output_bucket: str,
                     voice: str = 'female') -> str:
    """
    Génère un fichier MP3 de doublage FR depuis les segments traduits.
    Respecte les timestamps originaux avec des silences entre segments.
    Retourne la clé S3 du fichier audio final.
    """
    voice_id      = VOICES.get(voice, 'Lea')
    audio_chunks  = []   # Liste de bytes MP3 dans l'ordre
    last_end_time = 0.0  # Pour calculer les silences entre segments

    print(f"  Synthèse vocale avec Polly ({voice_id}) — {len(segments)} segments")

    for i, segment in enumerate(segments):
        start = segment['start']
        end   = segment['end']
        text  = segment['text'].strip()

        if not text:
            continue

        # Insérer un silence si nécessaire entre deux segments
        gap = start - last_end_time
        if gap > 0.05:  # > 50ms → on ajoute un silence
            silence_ms = int(gap * 1000)
            silence    = _generate_silence(silence_ms)
            audio_chunks.append(silence)

        # Durée disponible pour ce segment (en ms)
        duration_ms = int((end - start) * 1000)

        # Synthétiser le texte avec Polly
        audio = _synthesize_segment(text, voice_id, duration_ms)
        audio_chunks.append(audio)

        last_end_time = end

        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(segments)} segments traités...")

    # Assembler tous les chunks en un seul MP3
    final_audio = _concatenate_mp3(audio_chunks)

    # Uploader sur S3
    s3_key = f"dubbed/{episode_id}_fr.mp3"
    s3.put_object(
        Bucket=output_bucket,
        Key=s3_key,
        Body=final_audio,
        ContentType='audio/mpeg'
    )

    print(f"  Audio doublage uploadé : s3://{output_bucket}/{s3_key}")
    return s3_key


def _synthesize_segment(text: str, voice_id: str,
                         max_duration_ms: int) -> bytes:
    """
    Appelle Polly pour synthétiser un segment.
    Utilise le moteur Neural pour une voix plus naturelle.
    """
    # Limiter la longueur du texte si besoin (Polly max 3000 chars)
    if len(text) > 3000:
        text = text[:3000]

    try:
        response = polly.synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            OutputFormat='mp3',
            Engine='neural',          # Voix Neural = bien plus naturelle
            LanguageCode='fr-FR',
            SampleRate='22050',
        )
        return response['AudioStream'].read()

    except polly.exceptions.TextLengthExceededException:
        # Tronquer et réessayer
        return _synthesize_segment(text[:1500], voice_id, max_duration_ms)

    except Exception as e:
        print(f"  Avertissement Polly : {e} — segment ignoré")
        # Retourner un silence de la durée du segment
        return _generate_silence(max_duration_ms)


def _generate_silence(duration_ms: int) -> bytes:
    """
    Génère un silence MP3 de la durée spécifiée.
    On utilise Polly avec un texte SSML contenant un <break> silencieux.
    """
    # Clamp entre 1ms et 10s (limite Polly pour les breaks)
    duration_ms = max(1, min(duration_ms, 10000))

    response = polly.synthesize_speech(
        Text=f'<speak><break time="{duration_ms}ms"/></speak>',
        TextType='ssml',
        VoiceId='Lea',
        OutputFormat='mp3',
        Engine='neural',
        LanguageCode='fr-FR',
    )
    return response['AudioStream'].read()


def _concatenate_mp3(chunks: list[bytes]) -> bytes:
    """
    Concatène des fichiers MP3 en bytes.
    Pour de la démo c'est suffisant ; en production on utiliserait pydub
    pour un assemblage frame-precise.
    """
    # Assemblage brut — fonctionne bien pour des fichiers MP3 CBR
    buffer = io.BytesIO()
    for chunk in chunks:
        buffer.write(chunk)
    return buffer.getvalue()