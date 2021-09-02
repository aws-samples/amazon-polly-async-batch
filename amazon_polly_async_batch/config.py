# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import slugify
import uuid
import yaml


class Config:

    def __init__(self, stream):
        self.c = yaml.safe_load(stream)
        self.n = 0
        self.uuid = uuid.uuid4()

    def set_name(self):
        """
        Returns the name of the set -- a user-specified tag for the batch of Polly tasks
        """
        return self.c.get('set', {}).get('name', 'unnamed-set')

    def set_name_unique(self):
        """
        Returns the name of the set with a UUID as suffix
        :return: set name plus a UUID
        """
        return '{}-{}'.format(self.set_name(), self.uuid)

    def set_description(self):
        """
        Returns the optional description of the set
        :return set description
        """
        return self.c.get('set', {}).get('description', '')

    def output_s3_key_prefix(self):
        """
        Returns a prefix to use for this set of items
        """
        return self.c.get('set', {}).get('output-prefix', self.set_name())

    def defaults(self):
        """
        Returns the defaults for the file, which itself has defaults
        """
        defaults = self.c.get('defaults', {})
        return {
            'engine': defaults.get('engine', 'standard'),
            'language-code': defaults.get('language-code', 'en-US'),
            'output-format': defaults.get('output-format', 'mp3'),
            'text-type': defaults.get('text-type', 'text'),
            'voice-id': defaults.get('voice-id', 'Matthew')
        }

    def item_count(self):
        """
        Returns the number of items of work
        """
        return len(self.c.get('items', []))

    def items(self):
        """
        Return the items of work, with all the attributes properly set
        """
        for x in self.c.get('items', []):
            yield self.build_item(x, self.defaults())

    def build_item(self, item, defaults):
        """
        Given an item and the defaults, returns a dictionary that can be directly placed into the SQS queue
        :param item: the item from the config file, with perhaps few values
        :param defaults: the defaults from the config file
        :return: an item dict
        """
        rv = {
            'engine': item.get('engine', defaults['engine']),
            'language-code': item.get('language-code', defaults['language-code']),
            'output-format': item.get('output-format', defaults['output-format']),
            'output-s3-key-prefix': self.output_s3_key_prefix(),
            'text-type': item.get('text-type', defaults['text-type']),
            'voice-id': item.get('voice-id', defaults['voice-id']),
            'text': item.get('text'),
            'set-name': self.set_name_unique()
        }
        rv['output-file'] = '{}/{}'.format(self.output_s3_key_prefix(),
                                           item.get('output-file',
                                                    self.next_filename(item.get('text'), rv['output-format'])))
        self.n = self.n + 1
        return rv

    def next_filename(self, text, ext):
        """
        Returns the filename where the output should go
        """
        num = str(self.n).zfill(6)
        slug = slugify.slugify(text, max_length=40)
        return 'item-{}-{}.{}'.format(num, slug, ext)
