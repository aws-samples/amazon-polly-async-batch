# Operations

## DynamoDB Tables

As the solution processes your [set file](docs/set-file.md), information is stored
in two DynamoDB Tables.

### The Sets Table

Information about each set file submitted is stored in the `polly-batch-sets`
table. The partition key of this table is the `setName`, a globally unique
name that identifies the specific run of the set.

As work items are processed, the number of successes and failures are updated
in this table.

### The Items Table

Information about the specific items being synthesized are stored in the
`polly-batch-items` DynamoDB table.
