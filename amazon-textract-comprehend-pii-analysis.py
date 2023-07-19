import boto3
import logging
import os

# Retrieve environment variables
region_name = os.getenv(key='aws_region', default='us-east-1')
ddb_table = os.getenv(key='dynamodb_table')
uni_pii_list = os.getenv(key='universal_pii_types')
country_pii_list = os.getenv(key='country_pii_types')

# Create objects of Amazon Textract, Comprehend, S3, and DynamoDB
textract_obj = boto3.client('textract', region_name=region_name)
comprehend_obj = boto3.client('comprehend', region_name=region_name)
s3_obj = boto3.client('s3', region_name=region_name)
ddb_obj = boto3.resource('dynamodb', region_name=region_name).Table(ddb_table)

# Logging functionality
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S',
                    format='%(levelname)s: %(module)s:%(funcName)s:%(lineno)d: %(asctime)s: %(message)s')
LOG = logging.getLogger(__name__)

# Language code - as an input to Comprehend
LANG_EN = os.getenv(key='language_code', default='en')


def lambda_handler(event, context):
    """
    :param event: The event consists of the file name uploaded to the source S3 bucket.
    :param context:
    :return: The lambda processes the document uploaded through S3 bucket and calls Textract & Comprehend services.
    """
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    key_name = event['Records'][0]['s3']['object']['key']
    file_name = str(event['Records'][0]['s3']['bucket']['name']) + '/' + str(event['Records'][0]['s3']['object']['key'])
    LOG.info(f'File name is {file_name}')
    response = textract_obj.detect_document_text(Document={'S3Object': {'Bucket': bucket_name, 'Name': key_name}})
    LOG.info(f'Response is {response}')

    textract_resp_text = ''
    for item in response['Blocks']:
        if item['BlockType'] == 'LINE':
            textract_resp_text = textract_resp_text + ' ' + item['Text']

    if textract_resp_text:
        comprehend_entities = comprehend_obj.detect_pii_entities(Text=textract_resp_text, LanguageCode=LANG_EN)
        LOG.info('Comprehend Entities', comprehend_entities)
        buffer_list = []
        for entity in comprehend_entities['Entities']:
            LOG.info('Entity Type: '.format(entity['Type']))
            if entity['Type'] in uni_pii_list or country_pii_list:
                LOG.info('PII information captured in the document')
                buffer_list.append({'Type': entity['Type'], 'Confidence': entity['Score']})

        LOG.info(buffer_list)
        if len(buffer_list) > 0:
            ddb_obj.put_item(Item={'file_name': key_name, 'pii_confidence': str(buffer_list)})
        else:
            LOG.error(f'No PII data is captured from the document {key_name}')

    else:
        LOG.error(f'The document {key_name} is not processed!!')
