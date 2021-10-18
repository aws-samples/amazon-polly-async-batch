# Set File

A set file is a list of all text fragments that you want Polly to synthesize.
The process of synthesis is kicked off when you
upload the set file to the root of your S3 bucket.

Examples of valid set files are found in the [samples](samples) directory.

## Format

The set file is a simple YAML file, ending in the `.yml` extension.
It consists of a mandatory `set` section, an optional `defaults` section,
and a mandatory list of `items` to synthesize.

The [smallest valid set file](samples/minimal-set.yml) shows this.

### The `set` Section

- `name`: The name of this set, to differentiate it from others. These can be any
S3 (safe characters)[https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html],
but is typically something like `my-project`.
- `description`: An optional description
- `prefix`: An optional prefix for where the output files will go in S3. This
can be any S3 safe characters, but is typically something like `my-project-r2`.
If you don't specify a prefix, the `name` will be used.

### The `defaults` Section

This section sets defaults for all of the items in this set. Each default
value can be overridden by an item. If you don't include an attribute in the
`defaults` section, the solution will provide one for you.

- `engine`: The synthesis engine that Amazon Polly will use to turn the text
to speech. Either `neural` or `standard`; defaults to `neural`
- `language-code`: Any suppported language; defaults to `en-US`. Note that 
you need to make sure the language code matches the language spoken by the voice.
- `voice-id`: Any of the (supported voices)[https://docs.aws.amazon.com/polly/latest/dg/voicelist.html].
Note that the voice you choose must match the `language-code`, and not every
voice is supported in every engine. Defaults to `Matthew`.
- `text-type`: Either `text` or `ssml`; defaults to `text`.
- `output-format`: The file format you want the synthesized voice in, one of
`mp3`, `ogg_vorbis`, or `pcm`. Defaults to `mp3`.

### The `items` Section

For every separate file you want Amazon Polly to create, include a single
item in this section.

Each of the attributes in the `defaults` section above is valid, plus:

- `text`: The text to synthesize; mandatory. If the `text-type` for this item 
is `ssml`, then the value of this attribute should be valid SSML, for example
`<speak>hello</speak>`.
- `output-file`: The name of the file where you want the output to go. If you
don't include this attribute, the solution will create a unique filename for you
from the text and the order of the item.
