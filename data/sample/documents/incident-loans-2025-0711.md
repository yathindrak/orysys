# LND-2025-0711 Loan Document Delay

## Impact

Loan document generation was delayed for 42 minutes. Payment services were not affected.

## Root cause

The rendering queue accumulated work after a template service certificate expired. This incident did not involve database connection saturation.

## Resolution

The certificate was renewed and automated expiry monitoring was added.
