import json
import boto3
import os

# Step Functions クライアントを初期化
sfn = boto3.client('stepfunctions')

# 環境変数からステートマシンのARNを取得
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    for record in event['Records']:
        try:
            # SQSメッセージのbodyを取り出し
            body = json.loads(record['body'])
            inquiry_id = body.get('id')

            if not inquiry_id:
                print("Error: 'id' is missing in SQS message.")
                continue  # スキップして次のレコードへ

            # Step Functions ステートマシンの実行開始
            response = sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({ "id": inquiry_id })
            )

            print(f"[OK] Started execution for ID: {inquiry_id}")
            print(f"Execution ARN: {response['executionArn']}")

        except Exception as e:
            print(f"[ERROR] Failed to process record: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps("All messages processed.")
    }

