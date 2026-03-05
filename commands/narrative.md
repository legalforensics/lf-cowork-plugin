# /lf:narrative

Get a plain-English narrative walkthrough of a contract.

## Usage

```
/lf:narrative <contract_id>
```

## What it does

Calls `explain_contract` and presents a flowing, readable analysis:
- What the contract does in plain English
- Who holds the risk at each stage
- What breaks if things go wrong
- What a CEO or non-lawyer needs to know before signing

## Example

```
/lf:narrative 42
```

This is the most detailed analysis — ideal for pre-signature review or board briefings.
