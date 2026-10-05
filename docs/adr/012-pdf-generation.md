# ADR 012: SRS PDF Generation Pipeline

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
The system must export an IEEE 29148 / IEEE 830 compliant Software Requirements Specification with tables, matrices, and diagrams.

## Decision
Use Jinja2 HTML templates compiled to PDF via WeasyPrint, with ReportLab as an automated Windows fallback if GTK libraries are absent.

## Consequences
Pixel-perfect CSS typography, version-stamped header/footer blocks, and automatic watermarking of unapproved draft documents.
