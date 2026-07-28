# Hotel Cancellation Policy (Demo)

> ⚠️ **FICTIONAL DEMO POLICY — NOT LEGAL OR OFFICIAL ADVICE.**
>
> This document was written for a demonstration software project. Wanderlux Demo Travel is a
> fictional company. Nothing here reflects the real policies of any government,
> airline, hotel, insurer, or travel provider. For real travel requirements,
> always consult the official embassy, airline, or provider directly.


| Field | Value |
| --- | --- |
| policy_name | Hotel Cancellation Policy (Demo) |
| category | accommodation |
| destination | global |
| version | 1.0 |
| effective_date | 2026-01-01 |
| source | Wanderlux Demo Travel (fictional demo issuer) |

---

## 1. Scope

This demo policy governs cancellation of the mock hotel bookings held in the Wanderlux Demo Travel demo database. No real reservation, payment, or hotel is involved at any point.

## 2. Rate Types

Demo inventory offers three rate types. Flexible rates may be cancelled free of charge until 18:00 local hotel time on the day before arrival. Semi-flexible rates may be cancelled free until seven days before arrival, after which one night is charged. Non-refundable rates are charged in full from the moment of booking.

Where a rate type is not explicitly stated in the demo record, the planner assumes semi-flexible terms and says so in its assumptions.

## 3. Cancellation Fee Schedule

For semi-flexible bookings the demo schedule is: more than 7 days before arrival, no fee; 3 to 7 days, one night's charge; 24 to 72 hours, 50 percent of the total stay; less than 24 hours or no-show, 100 percent of the total stay.

## 4. Early Departure

Guests departing earlier than the confirmed checkout date are charged for the full original stay under this demo policy unless the booking was made on a flexible rate, in which case remaining nights are refunded less one night.

## 5. Peak Period Exceptions

During demo-designated peak periods — major festivals, new-year weeks, and large conventions — a stricter 14-day free-cancellation cut-off applies and deposits of one to three nights may be non-refundable.

## 6. Force Majeure and Extenuating Circumstances

Where travel becomes impossible because of natural disaster, government border closure, or a documented medical emergency, the demo policy allows a fee waiver at the property's discretion on production of supporting evidence. Travel insurance should be the primary remedy.

## 7. Group Bookings

Reservations of five or more rooms are treated as group bookings, with a 30-day free-cancellation cut-off and a permitted reduction of up to 10 percent of rooms without penalty inside that window.

## 8. How to Cancel in This Demo

Cancellation in this demo is performed through the operations agent, which calls the `cancel_booking` MCP tool. The booking's status changes to `cancelled` and the record is retained for audit — records are never hard-deleted. No money moves because no payment ever existed.

## 9. Refund Timing (Illustrative)

Where a refund would apply in a real deployment, the demo policy quotes 5 to 10 business days back to the original payment method after the property confirms the cancellation. See the Refund demo policy.

---

*End of demo document. Hotel Cancellation Policy (Demo), version 1.0, effective 2026-01-01. Issued by Wanderlux Demo Travel — a fictional entity created for a software demonstration.*
