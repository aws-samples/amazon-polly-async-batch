# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import json
import logging
import os
import sys

import dynamo

from botocore.config import Config

dynamodb = boto3.client('dynamodb')
polly = boto3.client('polly', config=Config(
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }))
sns = boto3.client('sns')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

RESPONSE_TOPIC_ARN = os.environ['RESPONSE_TOPIC_ARN']
WORK_BUCKET = os.environ['WORK_BUCKET']
SET_TABLE = os.environ['SET_TABLE']
TASK_TABLE = os.environ['TASK_TABLE']


def process_sqs_message(event, context):
    """
    Given a set of SQS messages in the event, each consisting of a number of text fragments to synthesize into speech,
    processes each in turn by posting them to Polly. Adds an in the DynamoDb WORK_TABLE for tracking each. Polly will
    synthesize the speech, place the generated sound file in the WORK_BUCKET, and notify the response topic.

    :param event: a set of items to synthesize into speech
    :param context: Ignored
    """
    try:
        successes, failures = 0, 0
        for record in event['Records']:
            payload = json.loads(record['body'])
            if process_item(payload) is not None:
                successes = successes + 1
            else:
                failures = failures + 1
        logger.info('Successfully processed {} items; {} failures.'.format(successes, failures))
    except Exception as ex:
        raise Exception('Failed to process SQS messages because {}'.format(str(ex)))


def process_item(item):
    """
    Given a work item consisting of text to synthesize, submits to Polly and tracks the response in DynamoDb.
    Retries up to 10 times if Polly is throttling us.

    :param item: a dictionary with details on a snippet of text to synthesize
    :return: the task ID assigned by Polly, or None if Polly refused the work
    """
    item_name = item.get('output-file', '[unidentified]')
    task_table = dynamo.TaskTable(TASK_TABLE)
    try:
        polly_task = submit_item_to_polly(item)
        task_table.put_new_task(polly_task, item, 'Task submitted')
        logger.debug('Posted item {} as polly task {}'.format(item_name, polly_task['TaskId']))
        return polly_task['TaskId']
    except Exception as e:
        logger.error('Failed to post item {} as polly task because {}'.format(item_name, str(e)))
        task_table.put_failed_task(item, str(e))
        dynamo.SetTable(SET_TABLE).post_failure(item['set-name'])
        return None


def submit_item_to_polly(work_item):
    """
    Given a work item in a dict, posts it as an asynchronous synthesis request to Polly.

    :param work_item: a dictionary with details on the text to synthesize
    :return: the json document returned from Polly
    """
    response = polly.start_speech_synthesis_task(
        Engine=work_item['engine'],
        LanguageCode=work_item['language-code'],
        OutputFormat=work_item['output-format'],
        OutputS3BucketName=WORK_BUCKET,
        OutputS3KeyPrefix=work_item['output-s3-key-prefix'],
        SnsTopicArn=RESPONSE_TOPIC_ARN,
        Text=work_item['text'],
        TextType=work_item['text-type'],
        VoiceId=work_item['voice-id']
    )
    return response['SynthesisTask']
