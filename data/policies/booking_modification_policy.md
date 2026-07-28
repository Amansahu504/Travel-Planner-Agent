# Booking Modification Policy (Demo)

> ⚠️ **FICTIONAL DEMO POLICY — NOT LEGAL OR OFFICIAL ADVICE.**
>
> This document was written for a demonstration software project. Wanderlux Demo Travel is a
> fictional company. Nothing here reflects the real policies of any government,
> airline, hotel, insurer, or travel provider. For real travel requirements,
> always consult the official embassy, airline, or provider directly.


| Field | Value |
| --- | --- |
| policy_name | Booking Modification Policy (Demo) |
| category | bookings |
| destination | global |
| version | 1.0 |
| effective_date | 2026-01-01 |
| source | Wanderlux Demo Travel (fictional demo issuer) |

---

## 1. Scope

This demo policy governs changes to existing mock bookings in the Wanderlux Demo Travel demo database, including dates, travellers, and components.

## 2. What Can Be Modified

The demo operations agent can change a booking's item, traveller name, status, and total cost through the `update_booking` MCP tool. Each change is written to the SQLite record and is immediately visible on retrieval.

Booking identifiers are never reused or reassigned, and records are never hard-deleted — a cancellation is recorded as a status change so the audit trail survives.

## 3. Change Fees (Illustrative)

The demo fee schedule is: hotel date change more than 7 days out, no fee; within 7 days, 25 USD plus any rate difference; flight date change, 80 USD plus fare difference; activity date change more than 48 hours out, no fee.

Rate and fare differences are always payable by the traveller, and a lower new rate does not generate a refund of the difference on non-flexible products.

## 4. Name Changes

Correcting a spelling of up to three characters is treated as a correction and carries no fee. Substituting a different traveller is treated as a cancellation and rebooking on flights, and as a free amendment on hotels and activities.

## 5. Adding and Removing Travellers

Additional travellers are subject to availability at prevailing demo rates. Removing a traveller applies the relevant cancellation policy to that person's share and may change the per-person rate for those who remain, particularly on twin-share accommodation.

## 6. Date Changes and Peak Periods

Moving a booking into a demo peak period incurs the peak rate difference and the stricter peak cancellation terms described in the Hotel Cancellation demo policy.

## 7. Modification Windows

Modifications are accepted up to 2 hours before a flight, 18:00 local time the day before a hotel arrival, and 24 hours before an activity. Later requests are handled as cancellations.

## 8. How Changes Are Requested in This Demo

The traveller asks the assistant in natural language — for example 'change my hotel booking' — and the host router delegates to the operations agent, which classifies the request as `update_booking` and calls the corresponding MCP tool. The agent will ask for the booking reference if it was not supplied.

## 9. Confirmation

Every successful modification returns the updated record. Travellers should check that the returned values match what they intended, since this demo issues no confirmation email.

---

*End of demo document. Booking Modification Policy (Demo), version 1.0, effective 2026-01-01. Issued by Wanderlux Demo Travel — a fictional entity created for a software demonstration.*
