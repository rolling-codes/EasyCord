# Security Policy

## Supported Versions

The following versions of EasyCord are currently being supported with active security patches.

| Version | Supported          |
| ------- | ------------------ |
| 5.x.x   | :white_check_mark: |
| 4.x.x   | :x:                |
| < 4.0   | :x:                |

## Reporting a Vulnerability

Contact meWe aim to acknowledge all reports within **48 hours**. Please do not disclose the vulnerability publicly until we have had a chance to investigate and release a patch.

## Scope & Vulnerability Taxonomy

### In-scope:
* Prompt injection vectors
* Privilege escalation
* Unauthorized data exposure

### Out-of-scope:
* Standard bugs
* Feature requests
* Intended administrative overrides

## Historical Baselines

To anchor expectations, here are some recent security fixes:
* **v5.48.0**: Resolved prompt injection vectors in `ai_moderator.py`.
* **v5.50.1**: Implemented AI Moderator governance (action guarding, rate limiting).
