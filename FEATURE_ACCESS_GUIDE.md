# How to Access New Features - Quick Guide

## 1. EMAIL OTP LOGIN 🔐

### How to Access:
1. **Open the app**: https://tally-report-ai.preview.emergentagent.com
2. You'll see the **Login Page** automatically
3. Enter your email address
4. Click "Send OTP"
5. Check your email for a 6-digit code
6. Enter the OTP and click "Verify & Login"
7. You're in!

### Features:
- ✅ Secure email-based authentication
- ✅ 6-digit OTP valid for 10 minutes
- ✅ Session lasts 7 days
- ✅ Beautiful email template with green theme
- ✅ Resend OTP option if needed
- ✅ Logout button in navigation (top right)

### Email Template:
```
╔════════════════════════════════════╗
║         TALLY REPORTS             ║
║   Your Login Verification Code    ║
╚════════════════════════════════════╝

        Your OTP Code
        
        ┌─────────────┐
        │   123456    │  ← Your 6-digit code
        └─────────────┘
        
   This code expires in 10 minutes
```

### Setup (IMPORTANT):
**You need a Resend API key for emails to work!**

1. **Get Resend API Key:**
   - Go to https://resend.com
   - Sign up (FREE: 100 emails/day)
   - Get your API key (starts with `re_`)

2. **Update Backend .env:**
   ```bash
   cd /app/backend
   nano .env
   ```
   
   Add this line:
   ```
   RESEND_API_KEY=re_your_actual_key_here
   SENDER_EMAIL=onboarding@resend.dev
   ```

3. **Restart Backend:**
   ```bash
   sudo supervisorctl restart backend
   ```

4. **Test:**
   - Go to login page
   - Enter YOUR real email
   - Click Send OTP
   - Check your inbox!

---

## 2. AI PURCHASE ORDER GENERATION 🤖

### How to Access:
1. Login to the app
2. Navigate to **"Inventory"** page (Package icon in nav)
3. Look for the **"AI Purchase Order"** button (top right, next to export buttons)
4. Click it!

### What Happens:
1. **AI Analysis Starts:**
   - GPT-5.2 analyzes all inventory items
   - Checks current stock vs reorder levels
   - Calculates sales velocity from transactions
   - Identifies urgent items needing immediate orders

2. **Modal Appears:**
   - Shows AI analysis summary
   - Lists items to order with:
     - **Priority badges**: URGENT/HIGH/MEDIUM/LOW (color-coded)
     - Current stock level
     - Reorder level
     - Recommended quantity to order
     - Estimated cost
     - Reason for ordering
   - Total estimated cost at bottom
   - Recommendations from AI

3. **Example Output:**
   ```
   AI Analysis:
   "3 items require immediate attention. Laptop inventory 
   is critically low with high sales velocity. Office chairs 
   nearing stockout. Recommend ordering within 48 hours."
   
   Items to Order:
   
   ┌─────────────────────────────────────────────────┐
   │ Laptop Dell Inspiron              🔴 URGENT    │
   │ Stock below reorder level, high sales velocity │
   │ Current: 10  Reorder: 50  Recommend: 100       │
   │ Est. Cost: ₹45,00,000                          │
   └─────────────────────────────────────────────────┘
   
   Total Estimated Cost: ₹1,50,000
   ```

### Features:
- ✅ AI-powered analysis using GPT-5.2
- ✅ Automatic priority classification
- ✅ Sales velocity calculation
- ✅ Cost estimation
- ✅ Actionable recommendations
- ✅ Beautiful modal UI
- ✅ Ready to approve and send to supplier

### Testing:
1. Make sure you have inventory items (sync data first)
2. Click "AI Purchase Order" button
3. Wait 3-5 seconds for AI to analyze
4. Modal opens with recommendations
5. Review items, costs, and priorities
6. Close or approve!

---

## 3. SALES FREQUENCY REPORT 📊

### How to Access:
1. Login to the app
2. Navigate to **"Analytics"** page (Activity icon)
3. Click **"Sales Frequency"** tab (3rd tab)
4. You'll see the report!

### Features:
- ✅ Transaction count per item
- ✅ Unique customer count per product
- ✅ Total quantity sold
- ✅ Total revenue per item
- ✅ Average quantity per transaction
- ✅ Top customer names listed
- ✅ **Date filter** (start date + end date)
- ✅ Summary cards at bottom

### Using Date Filter:
1. Click on "Start Date" input
2. Select date (e.g., 2026-01-01)
3. Click on "End Date" input  
4. Select date (e.g., 2026-01-31)
5. Report auto-updates!
6. See "Filtering: 2026-01-01 to 2026-01-31" message
7. Click "Clear Filters" to see all data

### Example Data:
```
┌────────────────────────────────────────────────────────────┐
│ Item           │ Txns │ Qty │ Customers │ Revenue │ Avg  │
├────────────────┼──────┼─────┼───────────┼─────────┼──────┤
│ Laptop Dell    │  2   │  9  │     2     │ 4,05,000│ 4.5  │
│ Office Chair   │  2   │ 22  │     2     │ 1,87,000│ 11.0 │
│ Printer HP     │  1   │  3  │     1     │  66,000 │ 3.0  │
└────────────────────────────────────────────────────────────┘

Top Customers: Tech Solutions Pvt Ltd, Corporate Hub Ltd
```

---

## VISUAL GUIDE

### 1. Login Page:
```
    🔒
TALLY REPORTS
Secure login with email OTP

┌─────────────────────────────────┐
│ Email Address                   │
│ 📧 your@email.com              │
│                                 │
│      [Send OTP]                │
│                                 │
│ A 6-digit OTP will be sent...  │
└─────────────────────────────────┘
```

### 2. Inventory Page with AI PO:
```
Inventory
                    [AI Purchase Order] [PDF] [Excel] [CSV]

[Search...] [Category Filter]

┌─────────────────────────────────────────────┐
│ Item Name    │ Qty │ Price │ Status       │
├──────────────┼─────┼───────┼──────────────┤
│ Laptop Dell  │ 45  │45,000 │ In Stock     │
│ Office Chair │ 120 │ 8,500 │ In Stock     │
└─────────────────────────────────────────────┘
```

### 3. Purchase Order Modal:
```
╔═══════════════════════════════════════════════╗
║  AI-Generated Purchase Order                  ║
║  Powered by GPT-5.2 Analysis                  ║
╠═══════════════════════════════════════════════╣
║                                               ║
║  AI Analysis:                                 ║
║  "3 items need immediate attention..."        ║
║                                               ║
║  Items to Order:                              ║
║  ┌─────────────────────────────────────────┐ ║
║  │ Laptop Dell Inspiron    🔴 URGENT      │ ║
║  │ Stock below reorder level              │ ║
║  │ Current: 10 → Order: 100               │ ║
║  │ Cost: ₹45,00,000                       │ ║
║  └─────────────────────────────────────────┘ ║
║                                               ║
║  Total: ₹1,50,000                            ║
║                                               ║
║  [Approve & Send]  [Close]                    ║
╚═══════════════════════════════════════════════╝
```

---

## TROUBLESHOOTING

### Login Not Working:
**Problem**: OTP not received
**Solution**: 
1. Check if RESEND_API_KEY is set in backend/.env
2. Restart backend: `sudo supervisorctl restart backend`
3. Check backend logs: `tail -50 /var/log/supervisor/backend.err.log`
4. Verify email is correct
5. Check spam folder

### AI Purchase Order Not Generating:
**Problem**: Button does nothing or shows error
**Solution**:
1. Check if inventory data exists (sync data first)
2. Verify EMERGENT_LLM_KEY has budget remaining
3. Check backend logs for AI errors
4. Try again (AI calls can timeout)

### Sales Frequency Empty:
**Problem**: "No sales data available"
**Solution**:
1. Sync data from Dashboard first
2. Check date filter (might be filtering everything out)
3. Click "Clear Filters" button
4. Ensure sales vouchers have items array populated

---

## API ENDPOINTS (for reference)

### Authentication:
- `POST /api/auth/send-otp` - Send OTP to email
- `POST /api/auth/verify-otp` - Verify OTP and login
- `POST /api/auth/verify-session` - Check if session valid
- `POST /api/auth/logout` - Logout user

### Purchase Order:
- `POST /api/inventory/generate-purchase-order` - Generate AI PO
- `GET /api/inventory/purchase-orders` - List all POs

### Sales Frequency:
- `GET /api/inventory/sales-frequency?start_date=&end_date=` - Get report

---

## SUMMARY

✅ **Login**: https://tally-report-ai.preview.emergentagent.com → Enter email → Get OTP → Login
✅ **AI PO**: Inventory page → "AI Purchase Order" button (top right)
✅ **Sales Freq**: Analytics page → "Sales Frequency" tab → Use date filters

**All features are now live and ready to use!** 🎉
