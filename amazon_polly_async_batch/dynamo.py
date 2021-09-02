# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import datetime
import logging
import uuid

dynamodb = boto3.client('dynamodb')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SetTable(object):

    def __init__(self, task_table):
        self.table_name = task_table

    def get_set(self, set_name):
        """
        Given a set ID returns that set record from Dynamo. Throws an exception if it's not found.
        :param set_name: the name of the set
        :return: the record
        """
        response = dynamodb.get_item(
            TableName=self.table_name,
            Key={'setName': {'S': set_name}}
        )
        if 'Item' in response:
            return response['Item']
        else:
            msg = 'Failed to load set {} from DynamoDb table {}'.format(set_name, self.table_name)
            raise Exception(msg)

    def put_new_set(self, s):
        """
        Given a set that we will soon be processing, writes it to Dynamo for tracking
        :param s: the file that we are processing
        """
        now = datetime.datetime.now()
        next_month = now + datetime.timedelta(days=+30)
        dynamodb.put_item(
            TableName=self.table_name,
            Item={
                'setName': {'S': s.set_name_unique()},
                'originalName': {'S': s.set_name()},
                'description': {'S': s.set_description()},
                'items': {'N': str(s.item_count())},
                'creationTime': {'S': now.isoformat()},
                'updatedTime': {'S': now.isoformat()},
                'expirationTime': {'S': next_month.isoformat()},
                'outputPrefix': {'S': s.output_s3_key_prefix()},
                'successes': {'N': '0'},
                'failures': {'N': '0'}
            }
        )

    def post_success(self, set_name):
        """
        Updates the set incrementing the successes field, and setting the updated date to now.
        :param set_name: the name of the set
        """
        dynamodb.update_item(
            TableName=self.table_name,
            Key={'setName': {'S': set_name}},
            UpdateExpression='ADD successes :num SET updatedTime = :when',
            ExpressionAttributeValues={':num': {'N': '1'},
                                       ':when': {'S': datetime.datetime.now().isoformat()}}
        )

    def post_failure(self, set_name):
        """
        Updates the set incrementing the failures field, and setting the updated date to now.
        :param set_name: the name of the set
        """
        dynamodb.update_item(
            TableName=self.table_name,
            Key={'setName': {'S': set_name}},
            UpdateExpression='ADD failures :num SET updatedTime = :when',
            ExpressionAttributeValues={':num': {'N': '1'},
                                       ':when': {'S': datetime.datetime.now().isoformat()}}
        )


class TaskTable(object):

    def __init__(self, task_table):
        self.table_name = task_table

    def get_task(self, task_id):
        """
        Given a task ID returns that task record from Dynamo. Throws an exception if it's not found.
        :param task_id: a task ID from Polly
        :return: the record
        """
        response = dynamodb.get_item(
            TableName=self.table_name,
            Key={'taskId': {'S': task_id}}
        )
        if 'Item' in response:
            return response['Item']
        else:
            msg = 'Failed to load task {} from DynamoDb table {}'.format(task_id, self.table_name)
            raise Exception(msg)

    def put_new_task(self, polly_task, work_item, message):
        """
        Given a dict of details of a task already submitted to Polly, and the work item that started it, adds a record
        to the task table for tracking. When the job is complete, a notification will be sent to the response processor,
        which will load this task detail and update the set records.
        :param polly_task: the return structure from Polly after the task was submitted
        :param work_item: the work item that we're processing
        :param message: a human-readable message describing the status as needed
        """
        now = datetime.datetime.now()
        next_month = now + datetime.timedelta(days=+30)
        dynamodb.put_item(
            TableName=self.table_name,
            Item={
                'taskId': {'S': polly_task.get('TaskId', str(uuid.uuid4()))},
                'taskStatus': {'S': polly_task.get('TaskStatus', 'failed')},
                'creationTime': {'S': now.isoformat()},
                'expirationTime': {'S': next_month.isoformat()},
                'outputUri': {'S': polly_task.get('OutputUri', '')},
                'outputKey': {'S': work_item.get('output-file', 'none')},
                'setName': {'S': work_item.get('set-name')},
                'message': {'S': message}
            }
        )

    def put_task(self, task_record):
        """
        Given an existing task record, just put it
        :param task_record:
        :return:
        """
        dynamodb.put_item(
            TableName=self.table_name,
            Item=task_record
        )

    def put_failed_task(self, work_item, message):
        """
        Stores a work item in the task table when Polly refused to accept it, for the reason given in `message`
        :param work_item: the work item
        :param message: A human-readable description of why polly refused to accept it
        :return:
        """
        self.put_new_task({}, work_item, message)
