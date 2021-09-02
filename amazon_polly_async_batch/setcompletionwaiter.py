# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import json
import logging
import os

import dynamo

from datetime import datetime

dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SET_TABLE = os.environ['SET_TABLE']
SET_COMPLETE_TOPIC_ARN = os.environ['SET_COMPLETE_TOPIC_ARN']
WORK_BUCKET = os.environ['WORK_BUCKET']


def load_set_details(event, context):
    """
    Loads details of a set (in `SET_TABLE`) and calculates how many tasks remain. This is the first step of a set of
    lambda step functions; it simply passes the current status to the next step.

    :param event: the event
    :param context: ignored
    """
    try:
        s = dynamo.SetTable(SET_TABLE).get_set(event['setName'])
        remaining = int(s['items']['N']) - int(s['successes']['N']) - int(s['failures']['N'])
        last_updated = datetime.fromisoformat(s['updatedTime']['S'])
        utc_now = datetime.utcnow()
        minutes_since_last_update = (utc_now - last_updated).total_seconds() / 60
        return {
            'setName': s['setName']['S'],
            'originalName': s['originalName']['S'],
            'description': s['description']['S'],
            'outputPrefix': s['outputPrefix']['S'],
            'successes': s['successes']['N'],
            'failures': s['failures']['N'],
            'updatedTime': s['updatedTime']['S'],
            'minutesSinceLastUpdate': minutes_since_last_update,
            'remaining': remaining
        }
    except Exception as e:
        logger.error('Failed to load set details because {}'.format(str(e)))
        raise e


def notify_of_set_completion(event, context):
    """
    Notifies the completion topic that all of the work has taken place, including how many succeeded and how many
    failed. Different subscription types get different payloads.

    :param event: the event
    :param context: ignored
    """
    try:
        set_name = event['setName']
        logger.info("Notifying of completion of set {}".format(set_name))
        desc = event['description']
        completed = '{}{}'.format(event['originalName'], ' ({})'.format(desc) if len(desc) > 0 else '')
        location = 's3://{}/{}/'.format(WORK_BUCKET, event['outputPrefix'])
        message_text = """
            Your Amazon Polly batch set {} completed with {} successful tasks and {} failures. The requested files are in {}.
        """.format(completed,
                   event['successes'],
                   event['failures'],
                   location)
        details = {
            'message': message_text,
            'set_name': set_name,
            'successes': event['successes'],
            'failures': event['failures'],
            'location': location
        }
        payload = {
            'default': json.dumps(details),
            'sms': 'Polly batch set {} completed'.format(event['originalName']),
            'email': message_text
        }
        sns.publish(
            TopicArn=SET_COMPLETE_TOPIC_ARN,
            Message=json.dumps(payload),
            Subject='Polly batch set {} completed'.format(event['originalName']),
            MessageStructure='json'
        )
    except Exception as e:
        logger.error('Failed to notify of set completion because {}'.format(str(e)))
        raise e


def notify_of_set_problem(event, context):
    """
    Notifies the completion topic that no updates have taken place in a long time. This clues the user in
    to the fact that something is wrong and the set likely was abandoned somehow.

    :param event: the event
    :param context: ignored
    """
    try:
        set_name = event['setName']
        logger.info("Notifying of problem with set {}".format(set_name))
        desc = event['description']
        problematic = '{}{}'.format(event['originalName'], ' ({})'.format(desc) if len(desc) > 0 else '')
        message_text = """
            There is a problem with your Polly batch set {}. No updates have been made since {}.
        """.format(problematic,
                   event['updatedTime'])
        details = {
            'message': message_text,
            'set_name': set_name,
            'no_updated_since': event['updatedTime']
        }
        payload = {
            'default': json.dumps(details),
            'sms': 'Problem with your Amazon Polly batch set {}'.format(event['originalName']),
            'email': message_text
        }
        sns.publish(
            TopicArn=SET_COMPLETE_TOPIC_ARN,
            Message=json.dumps(payload),
            Subject='Problem with your Amazon Polly batch set {}'.format(event['originalName']),
            MessageStructure='json'
        )
    except Exception as e:
        logger.error('Failed to notify of set problem because {}'.format(str(e)))
        raise e
