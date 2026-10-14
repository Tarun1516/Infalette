# DPDP (Digital Personal Data Protection) Compliance Guide

## Overview

The Digital Personal Data Protection Act (DPDP) 2023 is India's data protection law. Infalette complies with DPDP requirements for processing personal data of Indian users.

## Key Requirements

### 1. Consent Management

- **Explicit consent** required before collecting personal data
- **Purpose limitation** - data only used for stated purpose
- **Withdrawal** - users can withdraw consent at any time

**Implementation:**
- Consent checkboxes on checkout and registration forms
- Consent records stored in `events` table with `event_type: "consent_given"`
- Withdrawal endpoint: `POST /customers/{id}/withdraw-consent`

### 2. Data Minimization

- Only collect data necessary for the stated purpose
- No excessive data collection

**Implementation:**
- Checkout form only collects: name, email, phone, shipping address
- No unnecessary fields in registration

### 3. Data Retention

- Personal data retained only as long as necessary
- Default retention: 3 years after last order
- Automated cleanup via worker task

**Implementation:**
- `cleanup_old_events` worker task archives events older than 90 days
- Customer data anonymized after 3 years of inactivity

### 4. Data Subject Rights

Users have the right to:
- **Access** their personal data
- **Correct** inaccurate data
- **Erase** their data (right to be forgotten)
- **Port** their data to another service

**Implementation:**
- `GET /customers/{id}/data-export` - Download personal data
- `PATCH /customers/{id}` - Correct personal data
- `DELETE /customers/{id}` - Erase personal data (anonymized)
- `GET /customers/{id}/data-portability` - Export in machine-readable format

### 5. Security Measures

- **Encryption at rest** - Database encrypted with AES-256
- **Encryption in transit** - TLS 1.3 for all connections
- **Access control** - Role-based access (RBAC)
- **Audit logging** - All data access logged

### 6. Breach Notification

- Notify users within 72 hours of data breach
- Notify Data Protection Board of India

**Implementation:**
- Sentry alerts for security incidents
- Incident response runbook (see `docs/runbooks/incident-response.md`)
- Automated email notification to affected users

### 7. Children's Data

- No data collection from children under 18
- Age verification on checkout

### 8. Cross-Border Transfer

- Personal data of Indian users stored in India (Mumbai region)
- Transfer outside India only with user consent

## Compliance Checklist

- [x] Consent management implemented
- [x] Data minimization enforced
- [x] Data retention policy defined
- [x] Data subject rights endpoints implemented
- [x] Encryption at rest and in transit
- [x] Access control (RBAC)
- [x] Audit logging
- [x] Breach notification process
- [x] Age verification
- [x] Data localization (India region)