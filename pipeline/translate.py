# translate.py

import boto3
import time

translate_client = boto3.client('translate')

# Termes anime à ne pas traduire automatiquement
ANIME_GLOSSARY = {
    'Nakama':       'Nakama',        # Ami proche / compagnon
    'Hokage':       'Hokage',        # Chef village ninja
    'Ninjutsu':     'Ninjutsu',      # Techniques ninja
    'Jutsu':        'Jutsu',         # Technique / pouvoir
    'Sensei':       'Sensei',        # Professeur / mentor
    'Senpai':       'Senpai',        # Sénior respecté
    'Kouhai':       'Kouhai',        # Junior / élève
    'Dattebayo':    'Dattebayo',     # Interjection Naruto
    'Kunoichi':     'Kunoichi',      # Femme ninja
    'Shinobi':      'Shinobi',       # Ninja
    'Onii-chan':    'Onii-chan',     # Grand frère
    'Onee-chan':    'Onee-chan',     # Grande sœur
    'Nani':         'Nani',          # Quoi ?
    'Sugoi':        'Sugoi',         # Génial / incroyable
    'Baka':         'Baka',          # Idiot / stupide
    'Kawaii':       'Kawaii',        # Mignon
    'Senpai notice me': 'Senpai notice me', # Meme / expression
    'Itadakimasu':  'Itadakimasu',  # Avant de manger
    'Gomen':        'Gomen',         # Désolé
    'Yamete':       'Yamete',        # Arrête
    'Otsukaresama': 'Otsukaresama',  # Merci pour ton travail
    'Tsundere':     'Tsundere',      # Personnage froid qui cache ses sentiments
    'Yandere':      'Yandere',       # Personnage amoureux obsessionnel
    'Senpai':       'Senpai',        # Sénior / mentor
    'Shonen':       'Shonen',        # Manga pour garçons
    'Shojo':        'Shojo',         # Manga pour filles
    'Mecha':        'Mecha',         # Robot géant
    'Chibi':        'Chibi',         # Petit personnage mignon
    'OP':           'Opening',       # Générique d’ouverture
    'ED':           'Ending',        # Générique de fin
    'Kamehameha':   'Kamehameha',    # Technique Dragon Ball
    'Bankai':       'Bankai',        # Technique Bleach
    'Henshin':      'Henshin',       # Transformation
}

GLOSSARY_NAME = 'animefr-glossary'


def ensure_glossary_exists() -> str | None:
    """Crée le glossaire Translate si nécessaire. Retourne son ARN."""
    try:
        res = translate_client.get_terminology(Name=GLOSSARY_NAME,
                                               TerminologyDataFormat='CSV')
        print(f"  Glossaire existant : {GLOSSARY_NAME}")
        return res['TerminologyProperties']['Arn']
    except translate_client.exceptions.ResourceNotFoundException:
        pass

    # Construire le CSV du glossaire
    csv_lines = ['en,fr']
    for term_en, term_fr in ANIME_GLOSSARY.items():
        csv_lines.append(f'{term_en},{term_fr}')
    csv_data = '\n'.join(csv_lines).encode('utf-8')

    res = translate_client.import_terminology(
        Name=GLOSSARY_NAME,
        MergeStrategy='OVERWRITE',
        TerminologyData={'File': csv_data, 'Format': 'CSV'},
        Description='Termes spécifiques anime/manga — AniméFR'
    )
    arn = res['TerminologyProperties']['Arn']
    print(f"  Glossaire créé : {arn}")
    return arn


def translate_transcript(transcript: list[dict],
                          source_lang: str = 'en',
                          target_lang: str = 'fr') -> list[dict]:
    """
    Traduit chaque segment en conservant les timestamps.

    Entrée  : [{'start': 1.2, 'end': 3.4, 'text': 'Hello Naruto!'}]
    Sortie  : [{'start': 1.2, 'end': 3.4, 'text': 'Bonjour Naruto!',
                'original': 'Hello Naruto!'}]
    """
    glossary_arn = ensure_glossary_exists()
    translated   = []

    # Traitement par batch de 25 segments pour limiter les appels API
    batch_size = 25
    for i in range(0, len(transcript), batch_size):
        batch = transcript[i:i + batch_size]
        print(f"  Traduction segments {i+1}–{i+len(batch)} / {len(transcript)}")

        for segment in batch:
            result = _translate_segment(
                text=segment['text'],
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_arn=glossary_arn
            )
            translated.append({
                'start':    segment['start'],
                'end':      segment['end'],
                'text':     result,
                'original': segment['text']
            })

        # Petit délai pour respecter les rate limits
        if i + batch_size < len(transcript):
            time.sleep(0.5)

    print(f"  {len(translated)} segments traduits.")
    return translated


def _translate_segment(text: str, source_lang: str,
                        target_lang: str, glossary_arn: str | None) -> str:
    """Traduit un seul segment avec gestion des erreurs."""
    if not text.strip():
        return text

    kwargs = {
        'Text':               text,
        'SourceLanguageCode': source_lang,
        'TargetLanguageCode': target_lang,
    }
    if glossary_arn:
        kwargs['TerminologyNames'] = [GLOSSARY_NAME]

    try:
        res = translate_client.translate_text(**kwargs)
        return res['TranslatedText']
    except Exception as e:
        print(f"  Avertissement traduction : {e} — segment conservé en VO")
        return text  # Fallback : garder le texte original