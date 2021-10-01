# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from os import path
from amazon_polly_async_batch import config


def samples_dir():
    """Return the path to the directory with the samples files"""
    basepath = path.dirname(__file__)
    return path.abspath(path.join(basepath, '..', '..', 'docs', 'samples'))


def get_item(n):
    """Parse the valid-set.yml file and return the nth item"""
    with open('{}/valid-set.yml'.format(samples_dir()), 'r') as stream:
        cfg = config.Config(stream)
        # items() is a generator so convert to a list so we can subscript it
        items = [item for item in cfg.items()]
        return items[n]


def test_valid_parser():
    with open('{}/valid-set.yml'.format(samples_dir()), 'r') as stream:
        cfg = config.Config(stream)
        assert cfg.set_name() == 'poem-set'
        assert cfg.item_count() == 4
        assert cfg.set_name_unique().startswith('poem-set-')
        assert cfg.output_s3_key_prefix() == 'poem-set'


def test_sparse_item():
    item = get_item(0)
    assert item['engine'] == 'standard'
    assert item['language-code'] == 'en-US'
    assert item['output-format'] == 'mp3'
    assert item['text-type'] == 'text'
    assert item['voice-id'] == 'Matthew'
    assert item['text'] == 'April is the cruelest month, breeding'
    assert item['output-file'] == 'poem-set/item-000000-april-is-the-cruelest-month-breeding.mp3'
    assert item['set-name'].startswith('poem-set-')


def test_specify_output_file():
    item = get_item(1)
    assert item['engine'] == 'standard'
    assert item['language-code'] == 'en-US'
    assert item['output-format'] == 'mp3'
    assert item['text-type'] == 'text'
    assert item['voice-id'] == 'Matthew'
    assert item['text'] == 'Lilacs out of the dead land, mixing'
    assert item['output-file'] == 'poem-set/lilacs.mp3'


def test_default_overrides():
    item = get_item(2)
    assert item['text'] == 'Memory and desire, stirring'
    assert item['language-code'] == 'en-GB'
    assert item['voice-id'] == 'Amy'
    assert item['output-file'] == 'poem-set/item-000002-memory-and-desire-stirring.mp3'


def test_ssml():
    item = get_item(3)
    assert item['text-type'] == 'ssml'
    assert item['text'] == '<prosody pitch="low">Dull roots with spring rain.</prosody>'
    assert item['output-file'] == 'poem-set/item-000003-prosody-pitch-low-dull-roots-with-spring.mp3'
