# Onboarding Runbook

## New Tenant Onboarding

### 1. Create Tenant

```bash
# Create a new tenant via the API
curl -X POST http://localhost:8000/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Influencer Store",
    "slug": "influencer-store",
    "plan": "store"
  }'
```

### 2. Create Admin User

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@influencer-store.com",
    "password": "secure-password",
    "first_name": "Admin",
    "last_name": "User",
    "tenant_id": "<tenant_id_from_step_1>"
  }'
```

### 3. Configure Store

```bash
curl -X POST http://localhost:8000/stores \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Influencer Store",
    "slug": "influencer-store",
    "theme_config": {
      "colors": {
        "primary": "#6366f1",
        "secondary": "#8b5cf6"
      }
    }
  }'
```

### 4. Connect Instagram

1. Navigate to Settings > Integrations
2. Click "Connect Instagram"
3. Authorize via OAuth
4. Verify connection

### 5. Configure Payment Provider

#### Razorpay (India)
1. Navigate to Settings > Payments
2. Enter Razorpay Key ID and Secret
3. Set Webhook URL: `https://api.infalette.com/webhooks/razorpay`
4. Test connection

#### Stripe (International)
1. Navigate to Settings > Payments
2. Enter Stripe Secret Key
3. Set Webhook URL: `https://api.infalette.com/webhooks/stripe`
4. Test connection

### 6. Add Products

```bash
curl -X POST http://localhost:8000/products \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product Name",
    "description": "Product description",
    "price_cents": 99900,
    "sku": "PROD-001",
    "inventory_quantity": 100
  }'
```

### 7. Configure Domain

1. Navigate to Settings > Domain
2. Enter custom domain (e.g., `store.influencer.com`)
3. Add DNS records:
   - A record: `store.influencer.com` → `<server_ip>`
   - CNAME: `www.store.influencer.com` → `store.influencer.com`
4. Verify domain

### 8. Set Up Automation

1. Navigate to Automation > Create Rule
2. Select trigger (e.g., "Instagram Comment")
3. Configure conditions (e.g., "Contains keyword 'buy'")
4. Add actions (e.g., "Send DM with checkout link")
5. Activate rule

### 9. Verify Storefront

1. Visit `https://store.influencer.com`
2. Verify products are displayed
3. Test checkout flow
4. Verify payment processing

### 10. Monitor Analytics

1. Navigate to Analytics > Dashboard
2. Verify metrics are being collected
3. Set up alerts for low inventory
4. Configure weekly reports

## Troubleshooting

### Instagram Connection Issues
- Verify OAuth credentials
- Check webhook subscription
- Ensure Instagram account is business/creator

### Payment Failures
- Check Razorpay/Stripe credentials
- Verify webhook signatures
- Check payment provider dashboard

### Domain Not Working
- Verify DNS records
- Check SSL certificate
- Ensure domain is verified in admin

### Automation Not Triggering
- Check rule status (active)
- Verify trigger configuration
- Check automation logs
