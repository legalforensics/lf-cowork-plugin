# /lf:standards-check

Check a contract against your company's negotiation playbook.

## Usage

```
/lf:standards-check <contract_id>
/lf:standards-check <contract_id> playbook <playbook_id>
```

## What it does

Calls `run_standards_review` and returns:
- Which playbook standards are met / violated
- Specific clauses that deviate from policy
- Suggested language fixes for each deviation

## Example

```
/lf:standards-check 42
```
