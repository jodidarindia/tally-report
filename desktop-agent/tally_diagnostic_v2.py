#!/usr/bin/env python3
"""
Tally XML Diagnostic v2 - With longer timeouts
Run: python tally_diagnostic_v2.py
Requirements: pip install requests
"""

import requests
import sys
import os

TALLY_URL = "http://localhost:9000"
TIMEOUT = 90  # 90 seconds - Tally can be slow with large datasets

# Request 1: Stock Items using the SAME format that previously returned 3275 chars
INVENTORY_XML = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>All Stock Items</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="StockCollection" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<TYPE>Stock Item</TYPE>
<FETCH>Name, ClosingBalance, BaseUnits, Category, ClosingRate</FETCH>
</COLLECTION>
<OBJECT NAME="StockExport" TYPE="Report" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<FETCH>Name, ClosingBalance, BaseUnits, Parent, ClosingRate</FETCH>
<USE>StockCollection</USE>
</OBJECT>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

# Request 2: Sales Vouchers using SAME format that previously returned 163K chars
SALES_XML = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>Sales Vouchers</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<EXPLODEFLAG>Yes</EXPLODEFLAG>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="SalesCollection" ISMODIFY="No">
<TYPE>Voucher</TYPE>
<FETCH>VoucherNumber, Date, PartyLedgerName, Amount, VoucherTypeName</FETCH>
<FILTER>VoucherTypeFilter</FILTER>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="VoucherTypeFilter">
$$IsSales:$VoucherTypeName
</SYSTEM>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

# Request 3: Simple Stock Summary report (alternative)
STOCK_SUMMARY_XML = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>Stock Summary</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""

# Request 4: Company name
COMPANY_XML = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>$$CurrentCompany</ID>
</HEADER>
<BODY>
<DESC></DESC>
</BODY>
</ENVELOPE>"""

# Request 5: List of Ledgers (Customers)
LEDGER_XML = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>All Ledgers</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""


def send_request(name, xml_body):
    print(f"\n{'='*60}")
    print(f"  TEST: {name}")
    print(f"  Timeout: {TIMEOUT}s (please wait...)")
    print(f"{'='*60}")
    try:
        response = requests.post(
            TALLY_URL,
            data=xml_body.encode('utf-8'),
            headers={'Content-Type': 'text/xml'},
            timeout=TIMEOUT
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response length: {len(response.content)} bytes")
        raw = response.content.decode('utf-8', errors='replace')
        
        # Show first 3000 chars
        preview = raw[:3000]
        print(f"\n  --- First 3000 chars ---")
        print(preview)
        if len(raw) > 3000:
            print(f"\n  ... ({len(raw) - 3000} more chars truncated)")
            print(f"\n  --- Last 500 chars ---")
            print(raw[-500:])
        return raw
    except requests.exceptions.ReadTimeout:
        print(f"  TIMEOUT after {TIMEOUT}s - Tally took too long to respond")
        return None
    except requests.exceptions.ConnectionError:
        print(f"  ERROR: Cannot connect to Tally at {TALLY_URL}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    print("=" * 60)
    print("  TALLY XML DIAGNOSTIC v2 (longer timeouts)")
    print("  Tally URL:", TALLY_URL)
    print("  Timeout:", TIMEOUT, "seconds per request")
    print("=" * 60)

    # Connection check
    print("\nChecking connection...")
    try:
        r = requests.post(TALLY_URL, data="<ENVELOPE></ENVELOPE>".encode('utf-8'),
                         headers={'Content-Type': 'text/xml'}, timeout=5)
        print(f"Connection OK (HTTP {r.status_code})")
    except:
        print(f"FAILED - Cannot reach Tally at {TALLY_URL}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    results = {}
    
    # Run tests one by one
    results['company'] = send_request("Company Name", COMPANY_XML)
    results['inventory'] = send_request("Inventory (Stock Items)", INVENTORY_XML)
    results['stock_summary'] = send_request("Stock Summary Report", STOCK_SUMMARY_XML)
    results['sales'] = send_request("Sales Vouchers", SALES_XML)
    results['ledgers'] = send_request("All Ledgers", LEDGER_XML)

    # Save to files
    output_dir = "tally_xml_dumps"
    os.makedirs(output_dir, exist_ok=True)
    for name, content in results.items():
        if content:
            filepath = os.path.join(output_dir, f"{name}.xml")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved: {filepath}")

    print(f"\n{'='*60}")
    print(f"  DONE! Please share this output in the chat.")
    print(f"{'='*60}")
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
