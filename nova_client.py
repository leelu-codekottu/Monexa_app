import boto3
import os
from dotenv import load_dotenv

def init_nova_client():
    """Initialize Nova Pro client with credentials from env"""
    load_dotenv()
    
    try:
        client = boto3.client(
            service_name='bedrock-runtime',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        return client
    except Exception as e:
        print(f"Error initializing Nova client: {e}")
        return None

def get_nova_response(client, prompt, conversation_history=None):
    """Get response from Nova Pro"""
    if conversation_history is None:
        conversation_history = []
        
    messages = conversation_history + [{"role": "user", "content": [{"text": prompt}]}]
    
    try:
        body = {
            "modelId": "amazon.nova-pro-v1:0",
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": 4096,
                "temperature": 0.7,
                "topP": 0.9
            }
        }
        
        response = client.converse(
            modelId=body["modelId"],
            messages=body["messages"],
            inferenceConfig=body["inferenceConfig"]
        )
        
        return response['output']['message']['content'][0]['text']
    except Exception as e:
        print(f"Nova API error: {e}")
        return ""