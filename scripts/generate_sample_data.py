"""Generate the made-up sample data used by the demo report.

Every vendor, customer, account and amount here is fictional. Known data-quality
problems are planted on purpose (see PLANTED below) so the Data Checks table has
something to catch. Run from the repo root:  python scripts/generate_sample_data.py
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'sample-data'
OUT.mkdir(exist_ok=True)

# ---- master data -----------------------------------------------------------
VENDORS = {  # standard name: (account, pricing model)
    'NORTHLINE HAULAGE': ('501234567', 'flat'),        # flat 10,000, initial only
    'COASTAL FREIGHT CO': ('502345678', 'two-part'),   # 6,000 initial + 3,500 final
    'SAVANNA MOVERS': ('503456789', 'distance'),       # 8,000-15,500, initial only
    'REDHILL LOGISTICS': ('504567890', 'two-part-big'),  # 13,000 initial + 6,000 final
}
VENDOR_ALIASES = [  # name as typed on the form -> standard vendor
    ('NORTHLINE HAULAGE', 'NORTHLINE HAULAGE'), ('NORTHLINE', 'NORTHLINE HAULAGE'),
    ('COASTAL FREIGHT CO', 'COASTAL FREIGHT CO'), ('COASTAL FREIGHT', 'COASTAL FREIGHT CO'),
    ('SAVANNA MOVERS', 'SAVANNA MOVERS'), ('REDHILL LOGISTICS', 'REDHILL LOGISTICS'), ('REDHILL', 'REDHILL LOGISTICS'),
]
CUSTOMERS = [  # code, official name, city, region
    ('0002000101', 'ADOM STAR ENTERPRISE', 'KUMASI', 'ASHANTI'),
    ('0002000102', 'KWAME MENSAH AND SONS LIMITED', 'ACCRA', 'GREATER ACCRA'),
    ('0002000103', 'SUNRISE TRADING VENTURES', 'TAMALE', 'NORTHERN'),
    ('0002000104', 'GOLDEN GATE SUPPLIES', 'TAKORADI', 'WESTERN'),
    ('0002000105', 'MAAME ESI STORES', 'CAPE COAST', 'CENTRAL'),
    ('0002000106', 'NEW HOPE MINIMART', 'TECHIMAN', 'BONO EAST'),
    ('0002000107', 'BLESSED HANDS ENTERPRISE', 'ACCRA', 'ASHANTI'),   # city wrong in master on purpose
    ('0002000108', 'RIVERSIDE WHOLESALE LTD', 'HO', 'VOLTA'),
]
ALIASES = [  # name as typed -> customer code, optional city override
    ('ADOM STAR', '0002000101', ''),
    ('KWAME MENSAH & SONS', '0002000102', ''),
    ('BLESSED HANDS ENTERPRISE', '0002000107', 'KUMASI'),  # master says ACCRA; deliveries go to Kumasi
]
TYPED_CUSTOMERS = ['ADOM STAR', 'Adom Star Ent', 'KWAME MENSAH & SONS', 'SUNRISE TRADING VENTURE',
                   'GOLDEN GATE SUPPLIES LTD', 'MAAME ESI STORES', 'NEW HOPE MINI MART', 'BLESSED HANDS ENTERPRISE',
                   'RIVERSIDE WHOLESALE', 'JOE & JANE KIOSK']  # the last one is not in the master

# ---- orders ----------------------------------------------------------------
start = datetime(2026, 9, 1, 9, 0)
names = list(VENDORS)
typed_name = {'NORTHLINE HAULAGE': 'Northline', 'COASTAL FREIGHT CO': 'Coastal Freight',
              'SAVANNA MOVERS': 'Savana Movers', 'REDHILL LOGISTICS': 'REDHILL LOGISTICS'}  # 'Savana' = typo, fuzzy match
plates = ['GR 1204-21', 'GT 5521-23', 'AS 3307-22', 'GN 7740-24', 'GW 6120-20', 'AE 2219-25']
orders, deliveries = [], []
deliv_no = 8800000201
for i in range(30):
    v = names[i % 4]
    acct, model = VENDORS[v]
    oid = str(7100000101 + i)
    sub = start + timedelta(days=i)
    row = {
        'OrderID': oid, 'SubmittedDate': sub, 'AssignedDate': sub + timedelta(hours=1), 'ApprovedDate': sub + timedelta(hours=3),
        'Status': '', 'VendorNameTyped': typed_name[v], 'VendorAccount': acct, 'VehicleNumber': plates[i % len(plates)],
        'InvoiceAmount': None, 'InitialAmount': None, 'InitialRef': '', 'InitialPaidDate': None,
        'FinalAmount': None, 'FinalRef': '', 'CompletedDate': None,
    }
    inv = {'flat': 10000, 'two-part': 6000, 'distance': 8000 + (i * 750) % 7500, 'two-part-big': 13000}[model]
    row['InvoiceAmount'] = row['InitialAmount'] = inv
    row['InitialRef'] = f'PAY-I-{oid}'
    row['InitialPaidDate'] = sub + timedelta(days=1)
    row['Status'] = 'Initial Payment Made'
    if model.startswith('two-part'):
        row['FinalAmount'] = 3500 if model == 'two-part' else 6000
        row['FinalRef'] = f'PAY-F-{oid}'
        row['CompletedDate'] = sub + timedelta(days=4)
        row['Status'] = 'Final Payment Made'
    orders.append(row)
    for k in range(1 + i % 3):
        deliveries.append({'DeliveryID': str(deliv_no), 'OrderID': oid, 'CustomerNameTyped': TYPED_CUSTOMERS[(i + k) % 9]})
        deliv_no += 1

# ---- PLANTED problems (each one should appear on the Data checks page) --------
o = {r['OrderID']: r for r in orders}
o['7100000106']['FinalAmount'] = 7100000106                 # order number typed into the final amount (inflates totals)
o['7100000107']['VendorAccount'] = VENDORS['NORTHLINE HAULAGE'][0]  # Savanna trip paid to Northline's account
o['7100000112']['VendorAccount'] = '504567990'              # Redhill account with one digit wrong
o['7100000115']['FinalRef'] = o['7100000114']['FinalRef']   # one final payment ref used on two orders
o['7100000117'].update(InvoiceAmount=1000, InitialAmount=1000)  # missing zero on a flat-rate vendor
o['7100000121'].update(Status='Initial Payment Pending', InitialAmount=None, InitialRef='', InitialPaidDate=None)  # overdue
o['7100000122'].update(InitialAmount=None, InitialRef='', InitialPaidDate=None)  # final paid without initial
o['7100000124']['VehicleNumber'] = '0244123456'             # phone number in the vehicle field
o['7100000126']['InitialPaidDate'] = o['7100000126']['SubmittedDate'] - timedelta(days=2)  # paid before approval
o['7100000127'].update(InitialRef='')                       # initial payment never confirmed
o['7100000128'].update(VendorNameTyped='Bluewave Transport', VendorAccount='509876543')  # vendor not in master
o['7100000130'].update(Status='Pending Approval', ApprovedDate=None, InitialAmount=None, InitialRef='', InitialPaidDate=None,
                       FinalAmount=None, FinalRef='', CompletedDate=None)  # waiting for approval
o['7100000111']['OrderID'] = '8800000215'                   # a delivery number typed as the order number
deliveries.append({'DeliveryID': '8800000299', 'OrderID': 'PENDING', 'CustomerNameTyped': 'ADOM STAR'})  # not linked
deliveries.append({'DeliveryID': deliveries[3]['DeliveryID'], 'OrderID': '7100000129', 'CustomerNameTyped': 'MAAME ESI STORES'})  # same delivery on two orders
deliveries.append({'DeliveryID': '960001234', 'OrderID': '7100000129', 'CustomerNameTyped': 'JOE & JANE KIOSK'})  # invalid delivery number


def fmt(v):
    if v is None:
        return ''
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d %H:%M')
    return v


def write(name, rows, cols):
    with open(OUT / name, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([fmt(r[c]) if isinstance(r, dict) else fmt(c) for c in (cols if isinstance(r, dict) else r)])


write('orders.csv', orders, list(orders[0].keys()))
write('deliveries.csv', deliveries, ['DeliveryID', 'OrderID', 'CustomerNameTyped'])
write('vendors.csv', VENDOR_ALIASES, ['NameAsTyped', 'StandardVendor'])
write('customers.csv', CUSTOMERS, ['CustomerCode', 'OfficialName', 'City', 'Region'])
write('customer_aliases.csv', ALIASES, ['NameAsTyped', 'CustomerCode', 'CityOverride'])
print(f'wrote {len(orders)} orders and {len(deliveries)} deliveries to {OUT}')
