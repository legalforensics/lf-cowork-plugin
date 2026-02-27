# /lf:perspective

Re-analyze a contract from a specific negotiating perspective.

## Usage

```
/lf:perspective <contract_id> <perspective>
```

Valid perspectives: `buyer`, `seller`, `licensor`, `licensee`, `vendor`, `customer`, `neutral`

## What it does

Calls `set_perspective` to update the analysis viewpoint, then returns the updated risk summary
prioritized for the chosen perspective.

## Example

```
/lf:perspective 42 buyer
```

Use this when you've switched from evaluating as a vendor to evaluating as the customer,
or when preparing negotiation arguments for the other side.
