#!/usr/bin/env python3
"""
Tally XML Diagnostic Script
Run this on your Windows machine where TallyPrime is running.
It dumps the raw XML responses from Tally so we can see the exact format.

Usage: python tally_diagnostic.py
Requirements: pip install requests
"""

import requests
import sys
import os

TALLY_URL = "http://localhost:9000"

# ============================================================
# REQUEST 1: Simple Stock Item list (most common format)
# ============================================================
INVENTORY_XML_1 = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>All Stock Items</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""

# ============================================================
# REQUEST 2: Stock Summary report
# ============================================================
INVENTORY_XML_2 = """<ENVELOPE>
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

# ============================================================
# REQUEST 3: List of Stock Items via TDL Collection
# ============================================================
INVENTORY_XML_3 = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>List of Stock Items</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""

# ============================================================
# REQUEST 4: Sales Vouchers via Day Book
# ============================================================
SALES_XML_1 = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>20240401</SVFROMDATE>
<SVTODATE>20260331</SVTODATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""

# ============================================================
# REQUEST 5: Sales Vouchers - simple export
# ============================================================
SALES_XML_2 = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>Sales Register</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""

# ============================================================
# REQUEST 6: Company Info
# ============================================================
COMPANY_XML = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Companies</REPORTNAME>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""

# ============================================================
# REQUEST 7: Ledger (Customers)
# ============================================================
LEDGER_XML = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Ledgers</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<LEDGERNAME>Sundry Debtors</LEDGERNAME>
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""


def send_request(name, xml_body):
    """Send XML request to Tally and return raw response"""
    print(f"\n{'='*60}")
    print(f"  TEST: {name}")
    print(f"{'='*60}")
    try:
        response = requests.post(
            TALLY_URL,
            data=xml_body.encode('utf-8'),
            headers={'Content-Type': 'text/xml'},
            timeout=15
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response length: {len(response.content)} bytes")

        raw = response.content.decode('utf-8', errors='replace')

        # Show first 2000 chars
        preview = raw[:2000]
        print(f"\n  --- First 2000 chars ---")
        print(preview)
        if len(raw) > 2000:
            print(f"\n  ... ({len(raw) - 2000} more chars truncated)")
            # Also show last 500 chars
            print(f"\n  --- Last 500 chars ---")
            print(raw[-500:])

        return raw

    except requests.exceptions.ConnectionError:
        print(f"  ERROR: Cannot connect to Tally at {TALLY_URL}")
        print(f"  Make sure TallyPrime is running and ODBC server is enabled on port 9000")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    print("=" * 60)
    print("  TALLY XML DIAGNOSTIC TOOL")
    print("  Checking Tally at:", TALLY_URL)
    print("=" * 60)

    # First check if Tally is reachable
    print("\nChecking connection to Tally...")
    try:
        r = requests.post(TALLY_URL, data="<ENVELOPE></ENVELOPE>".encode('utf-8'),
                         headers={'Content-Type': 'text/xml'}, timeout=5)
        print(f"Connection OK (HTTP {r.status_code})")
    except:
        print(f"FAILED - Cannot reach Tally at {TALLY_URL}")
        print("Make sure TallyPrime is running with ODBC server enabled.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    results = {}

    # Run all diagnostic requests
    results['company'] = send_request("Company Info", COMPANY_XML)
    results['inventory_1'] = send_request("Inventory - Collection Export", INVENTORY_XML_1)
    results['inventory_2'] = send_request("Inventory - Stock Summary", INVENTORY_XML_2)
    results['inventory_3'] = send_request("Inventory - List of Stock Items", INVENTORY_XML_3)
    results['sales_1'] = send_request("Sales - Voucher Register", SALES_XML_1)
    results['sales_2'] = send_request("Sales - Sales Register", SALES_XML_2)
    results['ledger'] = send_request("Ledger (Sundry Debtors)", LEDGER_XML)

    # Save full responses to files
    output_dir = "tally_xml_dumps"
    os.makedirs(output_dir, exist_ok=True)

    for name, content in results.items():
        if content:
            filepath = os.path.join(output_dir, f"{name}.xml")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nSaved full response: {filepath}")

    print(f"\n{'='*60}")
    print(f"  DIAGNOSTIC COMPLETE")
    print(f"  Full XML dumps saved to: {os.path.abspath(output_dir)}/")
    print(f"{'='*60}")
    print(f"\nPlease share the contents of the following files:")
    print(f"  1. {output_dir}/inventory_1.xml (or whichever returned data)")
    print(f"  2. {output_dir}/sales_1.xml (or whichever returned data)")
    print(f"\nOr copy-paste the output above into the chat.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
