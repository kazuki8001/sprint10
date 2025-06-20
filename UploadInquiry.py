import json
import boto3
import uuid
import re
import os

# 環境変数からキューのURLを取得
QUEUE_URL = os.environ.get('QUEUE_URL')  # エラーハンドリング強化

def lambda_handler(event, context):
    # 1. 入力パラメータの空白チェック
    required_params = ['reviewText', 'userName', 'mailAddress']
    param_empty_check = [
        param for param in required_params 
        if param not in event or not str(event[param]).strip()
    ]

    if param_empty_check:
        return {
            'statusCode': 400,
            'body': json.dumps(f'Missing required parameter(s): {", ".join(param_empty_check)}')
        }

    # 2. 入力パラメータの取得
    reviewText = event["reviewText"]
    userName = event["userName"]
    mailAddress = event["mailAddress"]

    # 2.1 メールアドレスの形式チェック
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, mailAddress):
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid email format')
        }

    # 3. UUIDの生成
    item_id = str(uuid.uuid4())

    # 4. DynamoDBリソースの初期化
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('InquiryTable')
    print(f"[DEBUG] Table ARN: {table.table_arn}")

    # 5. 登録データの作成
    item = {
        'id': item_id,
        'reviewText': reviewText,
        'userName': userName,
        'mailAddress': mailAddress
    }

    try:
        print(f"[DEBUG] Writing to DynamoDB table: {table.name}")
        print(f"[DEBUG] Item to be written: {item}")
        
        response = table.put_item(Item=item)
        print(f"[DEBUG] PutItem response: {response}")

        # SQS送信
        sqs = boto3.client('sqs')
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({ 'id': item_id })
        )

    except Exception as e:
        print(f"[ERROR] Exception during processing: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing request: {str(e)}')
        }

    # 6. 正常終了レスポンス
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Inquiry saved and enqueued successfully!',
            'id': item_id
        })
    }
