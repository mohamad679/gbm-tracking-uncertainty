# Security Policy

## Supported versions

The current supported development line is `0.1.x` on Python 3.11-3.13.

## Reporting a vulnerability

Please do not include sensitive exploit details in a public issue. Use GitHub's private vulnerability reporting feature for this repository when available. If private reporting is unavailable, open a minimal issue requesting a private contact channel without publishing exploit details.

Security reports should include the affected version, environment, impact, reproduction conditions, and any proposed mitigation.

## Scope

Security-relevant areas include:

- unsafe archive handling or decompression abuse;
- path traversal or unintended filesystem writes;
- dependency or packaging compromise;
- CI/release workflow permission escalation;
- malformed artifact handling that can cause unintended execution or resource exhaustion.

This repository processes scientific data and artifacts; it is not a clinical system and must not be treated as medical-device software.
