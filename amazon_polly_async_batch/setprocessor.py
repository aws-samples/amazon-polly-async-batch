# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import dynamo
import json
import logging
import os
import urllib

import config

dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
sqs = boto3.resource('sqs')
sfn = boto3.client('stepfunctions')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ITEM_QUEUE = os.environ['ITEM_QUEUE']
SET_TABLE = os.environ['SET_TABLE']
SET_COMPLETE_WAITER_ARN = os.environ['SET_COMPLETE_WAITER_ARN']


def process_set(event, context):
    """
    Processes a set that is described in a YAML file. The set file describes the items to be processed and what
    defaults are to be used. For every item in the YAML file, this function posts a single message to SQS.

    :param event: the event raised when a yaml file hits the s3 bucket
    :param context: ignored
    """
    try:
        # Get the name of the config file to process from the event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
        # Process all the items in the config
        cfg = load_config(bucket, key)
        process_config(cfg)
        # Kick off the set complete waiter, which will wait for all the tasks to be done
        sfn.start_execution(stateMachineArn=SET_COMPLETE_WAITER_ARN,
                            name=cfg.set_name_unique(),
                            input=json.dumps({'setName': cfg.set_name_unique()}))
    except Exception as e:
        logger.error('Failed to fully process set file because {}'.format(str(e)))
        raise e


def process_config(cfg):
    """
    Stores the set details in DynamoDB, then processes all the items in the passed-in Config object.

    :param cfg: the config file
    """
    queue = get_queue(ITEM_QUEUE)
    count, successes, failures = 0, 0, 0
    dynamo.SetTable(SET_TABLE).put_new_set(cfg)
    for item in cfg.items():
        if post_item(queue, item, count):
            successes = successes + 1
        else:
            failures = failures + 1
        count = count + 1
    logger.info('Successfully posted {} items in set {} to {}; {} failures.'.format(successes, cfg.set_name_unique(),
                                                                                    ITEM_QUEUE, failures))


def load_config(bucket, key):
    """
    Given a bucket name and a key which contains a configuration file, loads it up and returns it as a Config object

    :param bucket: the S3 bucket where the config file is
    :param key: the key of the file
    :return: a populated Config object
    """
    try:
        # Pull down and parse the set file
        s3_object = s3.get_object(Bucket=bucket, Key=key)
        s3_object_content = s3_object['Body'].read().decode('utf-8')
        return config.Config(s3_object_content)
    except Exception as e:
        msg = 'Failed to load configuration file at {}/{} because {}'.format(bucket, key, str(e))
        raise Exception(msg)


def get_queue(name):
    """
    Returns the SQS queue object by name

    :param name: the name of the queue
    :return: the object
    """
    try:
        return sqs.get_queue_by_name(QueueName=name)
    except Exception as e:
        msg = 'Failed to find SQS queue {} because {}'.format(name, str(e))
        raise Exception(msg)


def post_item(queue, item, count):
    """
    Posts an item as a message to an SQS queue

    :param queue: the SQS queue
    :param item: the item to post
    :return: success of operation
    """
    item_name = item.get('output-file', '[unidentified]')
    # Neural voices have a much lower tps service quota, so put them all in the same group. This effectively
    # single-threads their processing. Standard voices can fan out more without trouble.
    item_group = 'neural' if item['engine'] == 'neural' else 'standard-{}'.format(count % 5)
    try:
        logger.debug('Posting item {} to queue group {}'.format(item_name, item_group))
        queue.send_message(MessageBody=json.dumps(item), 
            MessageGroupId=item_group,
            MessageDeduplicationId=item_name)
        return True
    except Exception as e:
        logger.error('Failed to post item for {} because {}'.format(item_name, str(e)))
        return False
