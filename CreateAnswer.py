import boto3
import os

dynamodb = boto3.resource('dynamodb')
bedrock_runtime = boto3.client('bedrock-agent-runtime')

# 環境変数から取得
TABLE_NAME = os.environ.get('INQUIRY_TABLE', 'InquiryTable')
KB_ID = os.environ.get('KB_ID')  # 例: "kb-xxxxxxxxxxxx"
MODEL_ARN = os.environ.get('MODEL_ARN')  # 例: "arn:aws:bedrock:ap-northeast-1::foundation-model/anthropic.claude-3-sonnet"

def lambda_handler(event, context):
    inquiry_id = event.get('id')
    if not inquiry_id:
        return {"statusCode": 400, "body": "Missing inquiry id"}

    # ① DynamoDBからreviewTextを取得
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'id': inquiry_id})
        item = response.get('Item')
        if not item or 'reviewText' not in item:
            return {"statusCode": 404, "body": "Inquiry not found or missing reviewText"}
    except Exception as e:
        return {"statusCode": 500, "body": f"Error accessing DynamoDB: {str(e)}"}

    question = item['reviewText']

    # ② Bedrock で回答生成
    try:
        result = bedrock_runtime.retrieve_and_generate(
            input={"text": question},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KB_ID,
                    "modelArn": MODEL_ARN
                }
            }
        )
        # 回答取得と判定
        answer = result.get("output", {}).get("text", "").strip()
        
        # Bedrockのよくある拒否応答リスト
        rejection_phrases = [
            "Sorry, I am unable to assist you with this request.",
            "I'm not able to help with that.",
            "Unfortunately, I can't help with that."
        ]
        
        if not answer or answer in rejection_phrases:
            answer = "申し訳ありませんが、適切な回答が見つかりませんでした。"
            
    except Exception as e:
        return {"statusCode": 500, "body": f"Error from Bedrock: {str(e)}"}

    # ③ 回答を DynamoDB に保存（update）
    try:
        table.update_item(
            Key={'id': inquiry_id},
            UpdateExpression='SET answer = :a',
            ExpressionAttributeValues={':a': answer}
        )
    except Exception as e:
        return {"statusCode": 500, "body": f"Failed to update DynamoDB: {str(e)}"}

    # ④ 成功レスポンス返却
    return {"statusCode": 200, "body": answer}
