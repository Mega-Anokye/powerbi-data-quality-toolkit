# Sample data

All of it is made up: vendors, customers, accounts, amounts and dates. Regenerate it with `python scripts/generate_sample_data.py`.

| File | Rows | What it holds |
|---|---|---|
| `orders.csv` | 30 | One row per order: dates, status, vendor as typed, account, vehicle, amounts, payment refs |
| `deliveries.csv` | 63 | Deliveries per order, with the customer name as typed |
| `vendors.csv` | 7 | Vendor names as typed on the form, mapped to the standard vendor |
| `customers.csv` | 8 | The official customer list (code, name, city, region) |
| `customer_aliases.csv` | 3 | Confirmed name mappings, plus one city override |

## Pricing patterns (so outliers have something to stand out from)

- **Northline Haulage:** a flat 10,000 per trip, initial payment only.
- **Coastal Freight Co:** 6,000 initial + 3,500 final.
- **Savanna Movers:** 8,000-15,500 by distance, initial payment only.
- **Redhill Logistics:** 13,000 initial + 6,000 final.

## Planted problems

| Order / row | Problem | Expected flag |
|---|---|---|
| 7100000106 | Order number typed into FinalAmount | High: Amount looks like an ID number |
| 7100000107 | Savanna trip paid to Northline's account | High: Wrong vendor account? |
| 7100000112 | Redhill account with one digit wrong | High: Wrong vendor account? |
| 7100000114 / 115 | Same final payment ref on two orders | High: Payment ref used twice |
| 7100000117 | 1,000 instead of 10,000 | High: Amount far below usual |
| 7100000121 | Approved, initial payment never made | High: Payment overdue |
| 7100000122 | Final paid, no initial | Medium: Final paid without initial |
| 7100000126 | Paid two days before it was submitted | Medium: Paid before approval |
| 7100000127 | Initial amount with no payment ref | Medium: Payment not confirmed |
| 7100000128 | "Bluewave Transport" is not in the vendor master | Medium: New vendor |
| 7100000130 | Still waiting for approval | Medium: Approval overdue |
| 8800000215 | A delivery number typed as the order number | Medium: Order number not valid (and its deliveries become unlinked) |
| Delivery 8800000299 | Order "PENDING" | Medium: Delivery not linked to an order |
| Delivery 8800000204 | Same delivery under two orders | Medium: Duplicate delivery |
| Delivery 960001234 | Nine digits | Low: Delivery number not valid |
| 7100000124 | Phone number in the vehicle field | Low: Vehicle number not valid |
| Several deliveries | "SUNRISE TRADING VENTURE", "NEW HOPE MINI MART", "JOE & JANE KIOSK" | Low: Customer not confirmed (fuzzy match or not found) |

"Savana Movers" (typo) is matched to Savanna Movers by the fuzzy vendor match, and "Blessed Hands Enterprise" gets the city KUMASI from the alias override even though the customer list says ACCRA.
