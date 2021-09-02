# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import datetime
import json
import logging
import os

import dynamo

dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SET_TABLE = os.environ['SET_TABLE']
TASK_TABLE = os.environ['TASK_TABLE']
WORK_BUCKET = os.environ['WORK_BUCKET']


def process_sns_message(event, context):
    """
    Called after Polly has completed synthesizing text, updates the task record in DynamoDb with the success or failure
    reported by Polly, and updates the set record in DynamoDb with another success or failure count.

    :param event: a response from Polly
    :param context: Ignored
    """
    try:
        successes, failures = 0, 0
        for record in event['Records']:
            try:
                process_record(record)
                successes = successes + 1
            except Exception as e:
                logger.error(str(e))
                failures = failures + 1
        logger.info('Successfully processed {} responses; {} failures.'.format(successes, failures))
    except Exception as ex:
        logger.error('Failed to process Polly response because {}'.format(str(ex)))
        raise ex


def process_record(record):
    """
    Given the response from Polly for a specific synthesize request, updates the DynamoDb records with the results

    :param record: a record as sent by Polly
    """
    message = record['Sns']['Message']
    contents = json.loads(message)
    task_id = contents['taskId']
    status = contents['taskStatus']
    if status == 'COMPLETED':
        process_completed_task(task_id, contents['outputUri'])
    else:
        process_failed_task(task_id, status)
    logger.debug('Task {} ended with status {}'.format(task_id, status))


def process_completed_task(task_id, uri):
    """
    Given a completed Polly task -- meaning that Polly could synthesize the text into speech, and that the output file
    is in S3 ready to be picked up -- renames the file to be the requested one and updates the DynamoDb record for
    the task with the status and completion time. Increments the success count on the set record.

    :param task_id: the Polly task ID
    :param uri: the path to the completed audio file
    """
    logger.debug('Successfully processed task {}; setting status to {}'.format(task_id, 'Task completed'))
    record = dynamo.TaskTable(TASK_TABLE).get_task(task_id)
    # Rename the generated file so it's what was specified in the config file
    prefix = 's3://{}/'.format(WORK_BUCKET)
    source = uri.replace(prefix, '') if uri.startswith(prefix) else uri
    target = record['outputKey']['S']
    logger.debug('Renaming generated Polly file {} to {}'.format(source, target))
    s3.copy_object(Bucket=WORK_BUCKET,
                   CopySource={'Bucket': WORK_BUCKET, 'Key': source},
                   Key=target)
    s3.delete_object(Bucket=WORK_BUCKET, Key=source)
    # Update the record in the tasks table
    record['message'] = {'S': 'Task completed'}
    update_task_and_set_table(record, True)


def process_failed_task(task_id, status):
    """
    Given a failed task from Polly, updates the tasks table with the details and increments the failure count on the
    set table.

    :param task_id: the task ID
    :param status: the status as returned from Polly
    """
    logger.warning('Failed to process task {}; status was {}'.format(task_id, status))
    record = dynamo.TaskTable(TASK_TABLE).get_task(task_id)
    update_task_and_set_table(record, False)


def update_task_and_set_table(task_record, success):
    """
    Updates the task table with a completion and increments the `successes` or `failures` field for the set with the
    newest values.

    :param task_record: the task record as it came from Dynamo
    :param success: boolean whether the task succeeded or not
    """
    # Update the task record to show status and completion time
    logger.debug('Updating task {}'.format(task_record['taskId']))
    task_record['completionTime'] = {'S': datetime.datetime.now().isoformat()}
    task_record['taskStatus'] = {'S': 'succeeded' if success else 'failed'}
    dynamo.TaskTable(TASK_TABLE).put_task(task_record)
    if success:
        dynamo.SetTable(SET_TABLE).post_success(task_record['setName']['S'])
    else:
        dynamo.SetTable(SET_TABLE).post_failure(task_record['setName']['S'])
