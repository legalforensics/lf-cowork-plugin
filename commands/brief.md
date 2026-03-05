# /lf:brief

Get a one-page decision brief for a contract — should you sign, negotiate, or walk away?

## Usage

```
/lf:brief <contract_id>
```

## What it does

Calls `get_verdict` and formats the result as a concise executive brief:
- Recommended decision (sign / negotiate / walk away)
- Top negotiation priorities if negotiating
- Risk-based reasoning in plain English
- Estimated exposure if signed as-is

## Example

```
/lf:brief 42
```
