import boto3
import os
import json
import re

# クライアント初期化（Claude 3 は us-east-1 のみ対応）
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
bedrock_info = boto3.client("bedrock", region_name="us-east-1")

# 環境変数からテーブル名とモデルIDを取得
TABLE_NAME = os.environ.get('INQUIRY_TABLE', 'InquiryTable')
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')

CATEGORIES = ["質問", "改善要望", "ポジティブな感想", "ネガティブな感想", "その他"]

def lambda_handler(event, context):
    # 0. 使用可能なモデルIDを確認
    try:
        available_models = bedrock_info.list_foundation_models()
        model_ids = [m['modelId'] for m in available_models.get('modelSummaries', [])]
        if MODEL_ID not in model_ids:
            raise ValueError(f"MODEL_ID '{MODEL_ID}' is not available. Available models: {model_ids}")
    except Exception as e:
        # Step Functions に渡す例外形式としてそのまま raise
        raise RuntimeError(f"Error checking model availability: {str(e)}")

    # 1. リクエストパラメータ取得
    inquiry_id = event.get('id')
    if not inquiry_id:
        raise ValueError("Missing inquiry id")

    # 2. DynamoDB から reviewText を取得
    table = dynamodb.Table(TABLE_NAME)
    try:
        response = table.get_item(Key={'id': inquiry_id})
        item = response.get('Item')
        if not item or 'reviewText' not in item:
            raise ValueError("Inquiry not found or missing reviewText")
        review_text = item['reviewText']
    except Exception as e:
        raise RuntimeError(f"Error reading DynamoDB: {str(e)}")

    # 3. Claude 3 Sonnet へのプロンプト作成
    full_prompt = f"""
あなたは問い合わせ内容を以下のカテゴリのいずれかに分類するAIアシスタントです。
カテゴリは以下の通りです：
「質問」「改善要望」「ポジティブな感想」「ネガティブな感想」「その他」

必ずカテゴリ名のみを日本語で1つだけ出力してください。

問い合わせ内容：
「{review_text}」
"""

    # 4. Bedrock モデル呼び出し
    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": 50,
                "temperature": 0.0
            })
        )

        result = json.loads(response['body'].read())

        # Claude の出力形式対応
        content_blocks = result.get("content", [])
        output_text = ""

        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                output_text += block.get("text", "")

        output_text = output_text.strip()
        print(f"[DEBUG] Claude output: {output_text}")

        # カテゴリ抽出
        match = re.search(r"(質問|改善要望|ポジティブな感想|ネガティブな感想|その他)", output_text)
        category = match.group(1) if match else "その他"

    except Exception as e:
        raise RuntimeError(f"Error from Bedrock: {str(e)}")

    # 5. DynamoDB にカテゴリ保存
    try:
        table.update_item(
            Key={'id': inquiry_id},
            UpdateExpression='SET Category = :c',
            ExpressionAttributeValues={':c': category}
        )
    except Exception as e:
        raise RuntimeError(f"Error updating DynamoDB: {str(e)}")

    # 6. ステートマシン用レスポンス（純粋なJSON）
    return {
        "id": inquiry_id,
        "category": category
    }
