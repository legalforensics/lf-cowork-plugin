# /lf:analyze

Perform a full AI risk analysis on a LegalForensics contract.

## Usage

```
/lf:analyze <contract_id>
/lf:analyze <contract_id> from the perspective of <buyer|seller|vendor|customer>
```

## What it does

1. Calls `get_risk_analysis` to retrieve the full risk analysis
2. Summarizes: overall risk posture, top 3-5 risk items, exposure bands (operational / financial / regulatory)
3. Surfaces recommended next steps

## Example

```
/lf:analyze 42
```

Returns a structured risk summary with clause-level citations from the contract.
