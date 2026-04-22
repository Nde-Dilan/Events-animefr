# subtitle.py

import boto3

s3 = boto3.client('s3')


def generate_srt(segments: list[dict], episode_id: str,
                  output_bucket: str) -> str:
    """
    Génère un fichier .SRT depuis les segments traduits et l'uploade sur S3.
    Retourne la clé S3 du fichier généré.
    """
    srt_content = _build_srt(segments)
    s3_key      = f"subtitles/{episode_id}.srt"

    s3.put_object(
        Bucket=output_bucket,
        Key=s3_key,
        Body=srt_content.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )

    print(f"  Fichier SRT uploadé : s3://{output_bucket}/{s3_key}")
    return s3_key


def _build_srt(segments: list[dict]) -> str:
    """
    Construit le contenu SRT.

    Format SRT standard :
    1
    00:00:01,230 --> 00:00:03,450
    Bienvenue au Village Caché de la Feuille.

    2
    00:00:04,100 --> 00:00:06,800
    Mon nom est Naruto Uzumaki !
    """
    lines = []
    for i, seg in enumerate(segments, start=1):
        start_ts = _seconds_to_srt_timestamp(seg['start'])
        end_ts   = _seconds_to_srt_timestamp(seg['end'])
        text     = seg['text'].strip()

        lines.append(str(i))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append('')  # Ligne vide entre chaque bloc

    return '\n'.join(lines)


def _seconds_to_srt_timestamp(seconds: float) -> str:
    """
    Convertit 3661.5 → "01:01:01,500"
    Format SRT : HH:MM:SS,mmm
    """
    total_ms  = int(seconds * 1000)
    ms        = total_ms % 1000
    total_s   = total_ms // 1000
    secs      = total_s % 60
    total_min = total_s // 60
    mins      = total_min % 60
    hours     = total_min // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"