# setup_lambda.py

import boto3
import json
import zipfile
import os

import time 

lambda_client = boto3.client('lambda')
s3            = boto3.client('s3')
iam           = boto3.client('iam')

FUNCTION_NAME   = 'animefr-orchestrator'
ROLE_NAME       = 'animefr-lambda-role'
SOURCE_BUCKET   = 'animefr-episodes'

def create_iam_role():
    """Rôle IAM que Lambda assume pour accéder aux services AWS."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
        role_arn = role['Role']['Arn']
        print(f"  Rôle créé : {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=ROLE_NAME)['Role']['Arn']
        print(f"  Rôle existant : {role_arn}")

    # Attacher les permissions nécessaires
    policies = [
        'arn:aws:iam::aws:policy/AmazonS3FullAccess',
        'arn:aws:iam::aws:policy/AmazonTranscribeFullAccess',
        'arn:aws:iam::aws:policy/TranslateFullAccess',
        'arn:aws:iam::aws:policy/AmazonPollyFullAccess',
        'arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess',
        'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess',
    ]
    for policy_arn in policies:
        iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
    
    # ATTENTE pour propagation IAM
    print("  Attente propagation IAM...")
    time.sleep(10)  # 10-15 secondes suffisent généralement
    return role_arn

def zip_lambda_code():
    """Zippe le code Lambda pour le déploiement."""
    with zipfile.ZipFile('/tmp/lambda.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
        for folder in ['lambda', 'pipeline']:
            for root, _, files in os.walk(folder):
                for file in files:
                    filepath = os.path.join(root, file)
                    zf.write(filepath)
    print("  Code zippé : /tmp/lambda.zip")

def deploy_lambda(role_arn):
    """Crée ou met à jour la fonction Lambda."""
    with open('/tmp/lambda.zip', 'rb') as f:
        code = f.read()

    try:
        fn = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime='python3.12',
            Role=role_arn,
            Handler='lambda.handler.lambda_handler',
            Code={'ZipFile': code},
            Timeout=900,       # 15 minutes max
            MemorySize=512,
            Environment={
                'Variables': {
                    'OUTPUT_BUCKET': 'animefr-outputs',
                    'AUDIO_BUCKET':  'animefr-audio',
                }
            }
        )
        fn_arn = fn['FunctionArn']
        print(f"  Lambda créée : {fn_arn}")
    except lambda_client.exceptions.ResourceConflictException:
        fn = lambda_client.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=code
        )
        fn_arn = fn['FunctionArn']
        print(f"  Lambda mise à jour : {fn_arn}")

    return fn_arn

def add_s3_trigger(fn_arn):
    """Branche le bucket S3 sur la Lambda."""
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Permission pour que S3 invoque Lambda
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId='s3-trigger',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{SOURCE_BUCKET}',
            SourceAccount=account_id
        )
    except lambda_client.exceptions.ResourceConflictException:
        pass  # Permission déjà existante

    # Notification S3 → Lambda sur chaque nouveau .mp4
    s3.put_bucket_notification_configuration(
        Bucket=SOURCE_BUCKET,
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': fn_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {'FilterRules': [
                        {'Name': 'suffix', 'Value': '.mp4'}
                    ]}
                }
            }]
        }
    )
    print(f"  Trigger S3 configuré : tout .mp4 dans {SOURCE_BUCKET} → Lambda")

if __name__ == '__main__':
    print("Setup Lambda & trigger S3...")
    role_arn = create_iam_role()
    zip_lambda_code()
    fn_arn   = deploy_lambda(role_arn)
    add_s3_trigger(fn_arn)
    print("\nÉtape 2 terminée.")