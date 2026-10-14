# E-Commerce Rules Compliance Guide

## Overview

Infalette complies with the Consumer Protection (E-Commerce) Rules, 2020 and related Indian e-commerce regulations.

## Key Requirements

### 1. Seller Information Disclosure

Every storefront must display:
- Legal name of the seller
- Registered address
- Contact details (email, phone)
- GSTIN
- Return/refund policy
- Terms and conditions

**Implementation:**
- Store settings include all required fields
- Storefront footer displays seller information
- `GET /stores/{id}/legal` endpoint returns legal information

### 2. Product Information

Products must display:
- Clear product description
- Price (inclusive of all taxes)
- Country of origin
- MRP vs selling price
- Stock availability
- Delivery timeline

**Implementation:**
- Product model includes all required fields
- Storefront product page displays all information
- Price displayed as "₹X (incl. of all taxes)"

### 3. Pricing Transparency

- All prices must be inclusive of GST
- MRP must be displayed if different from selling price
- No hidden charges at checkout

**Implementation:**
- `TaxService` calculates GST and includes in price
- Checkout shows itemized breakdown (subtotal, tax, shipping, discount)
- No surprise charges at payment

### 4. Return and Refund Policy

- Clear return policy (minimum 7 days for most products)
- Refund timeline: 7-10 business days
- Return shipping policy clearly stated

**Implementation:**
- `OrderService` supports returns and refunds
- Refund processed via original payment method
- Return policy displayed on product page and checkout

### 5. Grievance Redressal

- Grievance officer designated for each marketplace
- Contact details displayed on storefront
- Response within 48 hours of complaint

**Implementation:**
- Grievance officer details in store settings
- `POST /customers/{id}/grievance` endpoint for complaints
- Auto-acknowledgment email sent immediately

### 6. Data Protection

- Comply with DPDP Act (see `dpdp.md`)
- No sharing of customer data with third parties without consent
- Secure payment processing

### 7. Advertising Standards

- No misleading advertisements
- Clear product images (no deceptive editing)
- Honest product descriptions

**Implementation:**
- Product validation prevents misleading titles
- Image guidelines in admin documentation

### 8. Inventory Accuracy

- Display accurate stock levels
- No selling out-of-stock items (unless pre-order)
- Notify customers of stock changes

**Implementation:**
- `InventoryService` tracks stock in real-time
- Cart prevents adding out-of-stock items
- Order cancellation if stock unavailable

### 9. Delivery Commitments

- Display estimated delivery time
- Track shipment status
- Notify customers of delays

**Implementation:**
- `ShippingService` calculates delivery estimates
- Order tracking via `GET /orders/{id}/tracking`
- Email/SMS notifications for status changes

### 10. Payment Security

- PCI DSS compliance via Razorpay/Stripe
- No storage of card details
- Secure payment pages

**Implementation:**
- Payments processed via Razorpay/Stripe (PCI DSS compliant)
- No card data stored in database
- Webhook signatures verified

## Compliance Checklist

- [x] Seller information disclosure
- [x] Product information display
- [x] Pricing transparency (GST inclusive)
- [x] Return and refund policy
- [x] Grievance redressal mechanism
- [x] Data protection (DPDP compliance)
- [x] Advertising standards
- [x] Inventory accuracy
- [x] Delivery commitments
- [x] Payment security (PCI DSS via providers)