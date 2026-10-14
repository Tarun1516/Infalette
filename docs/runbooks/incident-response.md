# Incident Response Runbook

## Incident Severity Levels

### P0 - Critical (Service Down)
- Complete API outage
- Database corruption
- Payment processing failure
- **Response Time**: Immediate (24/7)
- **Escalation**: Page on-call engineer

### P1 - High (Major Feature Broken)
- Checkout flow broken
- Instagram/WhatsApp integration down
- Admin dashboard inaccessible
- **Response Time**: 15 minutes
- **Escalation**: Notify team lead

### P2 - Medium (Minor Feature Broken)
- Analytics delay
- Email notifications delayed
- Single tenant issue
- **Response Time**: 1 hour
- **Escalation**: Create ticket

### P3 - Low (Cosmetic/Minor)
- UI bugs
- Non-critical feature issues
- **Response Time**: Next business day
- **Escalation**: Add to backlog

## Response Steps

### 1. Detect
- Sentry alert
- User report
- Monitoring dashboard
- Health check failure

### 2. Assess
- Determine severity (P0-P3)
- Identify affected services
- Estimate number of affected users
- Check recent deployments

### 3. Contain
- Roll back recent deployment if needed
- Disable affected feature flag
- Scale up resources if overloaded
- Block malicious traffic

### 4. Resolve
- Apply hotfix
- Restart affected services
- Clear cache if needed
- Verify resolution

### 5. Post-Mortem
- Create incident report within 48 hours
- Document timeline
- Identify root cause
- Create action items to prevent recurrence

## Common Incidents

### API Down
1. Check `docker-compose ps` for container status
2. Check database connectivity: `pg_isready -h localhost`
3. Check Redis: `redis-cli ping`
4. Review API logs: `docker-compose logs api`
5. Restart if needed: `docker-compose restart api`

### Database Issues
1. Check connection pool: `SELECT count(*) FROM pg_stat_activity`
2. Check for locks: `SELECT * FROM pg_locks WHERE NOT granted`
3. Check disk space: `df -h`
4. Review slow queries: `SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10`

### Payment Failures
1. Check Razorpay/Stripe status pages
2. Verify webhook signatures
3. Check payment provider credentials
4. Review payment logs in admin

### Instagram/WhatsApp Webhook Failures
1. Check webhook subscription status
2. Verify webhook URL is accessible
3. Check for rate limiting
4. Review webhook handler logs
