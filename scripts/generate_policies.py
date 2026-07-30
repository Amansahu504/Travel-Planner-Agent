"""Generate the 10 demo travel-policy documents served by MCP Server 3.

IMPORTANT: these are FICTIONAL sample policies for a made-up demo company
("Wanderlux Demo Travel"). They are deliberately NOT presented as real
government, airline, or hotel policies — every document carries a demo banner.
Each document is roughly 2-3 pages of markdown.

Run: uv run python -m scripts.generate_policies
"""
from __future__ import annotations

from common.config import POLICY_DOCS_DIR

COMPANY = "Wanderlux Demo Travel"
VERSION = "1.0"
EFFECTIVE = "2026-01-01"

BANNER = f"""> ⚠️ **FICTIONAL DEMO POLICY — NOT LEGAL OR OFFICIAL ADVICE.**
>
> This document was written for a demonstration software project. {COMPANY} is a
> fictional company. Nothing here reflects the real policies of any government,
> airline, hotel, insurer, or travel provider. For real travel requirements,
> always consult the official embassy, airline, or provider directly.
"""


def _doc(title: str, category: str, destination: str, sections: list[tuple[str, list[str]]]) -> str:
    out = [
        f"# {title}",
        "",
        BANNER,
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| policy_name | {title} |",
        f"| category | {category} |",
        f"| destination | {destination} |",
        f"| version | {VERSION} |",
        f"| effective_date | {EFFECTIVE} |",
        f"| source | {COMPANY} (fictional demo issuer) |",
        "",
        "---",
        "",
    ]
    for heading, paragraphs in sections:
        out += [f"## {heading}", ""]
        for para in paragraphs:
            out += [para, ""]
    out += [
        "---",
        "",
        f"*End of demo document. {title}, version {VERSION}, effective "
        f"{EFFECTIVE}. Issued by {COMPANY} — a fictional entity created for a "
        "software demonstration.*",
        "",
    ]
    return "\n".join(out)


POLICIES: dict[str, dict] = {
    "visa": {
        "filename": "visa_policy.md",
        "title": "Visa Policy (Demo)",
        "category": "entry_requirements",
        "destination": "global",
        "sections": [
            ("1. Purpose and Scope", [
                f"This demo policy explains how {COMPANY} handles visa guidance for "
                "travellers booking through the platform. It applies to all leisure and "
                "business itineraries created in the demo environment and covers the "
                "traveller's responsibilities, our advisory role, and the limits of that "
                "advice.",
                "Visa rules are set by sovereign governments and change frequently. Any "
                "guidance surfaced by this system is an illustrative planning aid only. "
                "The traveller remains solely responsible for holding valid entry "
                "documents at check-in and at the border.",
            ]),
            ("2. Traveller Responsibilities", [
                "Travellers must confirm the entry requirements for their nationality "
                "with the destination country's embassy or official immigration portal "
                "before booking non-refundable travel. Requirements can differ based on "
                "nationality, purpose of travel, length of stay, and any transit points.",
                "Travellers should verify: whether a visa is required in advance, whether "
                "a visa-on-arrival or electronic travel authorisation is available, the "
                "permitted length of stay, the number of permitted entries, and any proof "
                "of onward travel, accommodation, or funds that may be requested.",
                "Where a transit country requires a separate transit visa — even for "
                "passengers who do not leave the airport — obtaining that visa is the "
                "traveller's responsibility.",
            ]),
            ("3. Advisory Service Provided", [
                "In this demo, the planning agent may include a general note about likely "
                "visa considerations for a destination. That note is generated from "
                "sample knowledge content and must be treated as a prompt to check "
                "official sources, never as a determination of eligibility.",
                "The system will not: assess an individual's eligibility, complete or "
                "submit visa applications, guarantee processing times, or predict the "
                "outcome of any application.",
            ]),
            ("4. Recommended Processing Timelines (Illustrative)", [
                "For demo planning purposes only, assume the following indicative "
                "windows: electronic travel authorisations may be issued within a few "
                "business days; standard tourist visas commonly take two to four weeks; "
                "and applications requiring an in-person appointment or additional "
                "documentation may take six weeks or longer during peak season.",
                "Travellers are advised to begin the process at least eight weeks before "
                "departure and to avoid booking non-refundable components until entry "
                "documentation is secured.",
            ]),
            ("5. Passport Validity Interaction", [
                "Many destinations require a passport valid for at least six months "
                "beyond the intended departure date, plus one or more blank pages. "
                "Travellers whose passport falls short of this should renew before "
                "applying for any visa. See the companion Passport Requirements demo "
                "policy for details.",
            ]),
            ("6. Denied Entry and Refunds", [
                "If a traveller is denied boarding or entry because of missing or invalid "
                "documentation, the booking is treated as a no-show. Under this demo "
                "policy, no refund is issued for the affected components, and any "
                "applicable supplier cancellation terms apply.",
                "Travellers are strongly encouraged to hold travel insurance that "
                "includes documentation-related trip interruption cover. See the Travel "
                "Insurance demo policy.",
            ]),
            ("7. Group and Family Bookings", [
                "For group itineraries, each traveller must independently satisfy entry "
                "requirements. A confirmed visa for one member of a party confers no "
                "status on any other member. Minors may require additional consent "
                "documentation where they travel with only one parent or guardian.",
            ]),
            ("8. Data Handling", [
                "The demo system does not collect, store, or transmit passport numbers, "
                "visa numbers, or other identity-document data. Users of this demo should "
                "never enter real identity-document details into the interface.",
            ]),
            ("9. Escalation and Support", [
                "Questions about this demo policy can be directed to the fictional "
                "support desk of the demo issuer. In a production deployment, this "
                "section would name the responsible team, service-level targets, and an "
                "escalation path for time-critical documentation issues.",
            ]),
        ],
    },
    "passport": {
        "filename": "passport_policy.md",
        "title": "Passport Requirements Policy (Demo)",
        "category": "entry_requirements",
        "destination": "global",
        "sections": [
            ("1. Purpose", [
                f"This demo policy sets out the passport standards {COMPANY} asks "
                "travellers to meet before travel is booked, and how the platform "
                "handles passport-related risk in itinerary planning.",
            ]),
            ("2. Six-Month Validity Rule", [
                "Travellers should hold a passport valid for at least six months beyond "
                "the planned date of departure from the destination. Several countries "
                "enforce this strictly and will deny boarding where it is not met, even "
                "when a valid visa has been issued.",
                "Where a traveller's passport expires within six months of return, this "
                "demo system will surface a warning in the itinerary's assumptions and "
                "warnings section.",
            ]),
            ("3. Blank Pages", [
                "At least two facing blank pages should be available for entry and exit "
                "stamps. Some destinations require more where a visa label is affixed. "
                "Travellers close to running out of pages should renew early.",
            ]),
            ("4. Condition and Damage", [
                "Passports with water damage, a detached or torn photo page, an unreadable "
                "machine-readable zone, or unofficial annotations may be rejected. Border "
                "officials have full discretion. Travellers should replace a damaged "
                "passport well before departure.",
            ]),
            ("5. Name Matching", [
                "The traveller name on every booking must match the passport exactly, "
                "including middle names where the passport shows them. Mismatches are a "
                "common cause of denied boarding.",
                "Under this demo policy, name corrections requested more than 72 hours "
                "before departure are handled as a modification (see the Booking "
                "Modification demo policy). Corrections inside 72 hours may require "
                "cancellation and rebooking at prevailing rates.",
            ]),
            ("6. Dual Nationality", [
                "Dual nationals should confirm which passport to present at each border, "
                "as some countries require their own nationals to enter and exit on the "
                "national passport. The itinerary should be booked on the passport that "
                "will actually be presented.",
            ]),
            ("7. Lost or Stolen Passports Abroad", [
                "Travellers who lose a passport abroad should report it to local police "
                "and contact their nearest embassy or consulate for an emergency travel "
                "document. Recovery typically requires proof of identity and citizenship, "
                "a police report, and passport photographs.",
                "This demo policy recommends carrying a separate photocopy or secure "
                "digital copy of the passport data page, stored apart from the passport "
                "itself.",
            ]),
            ("8. Children's Passports", [
                "Children's passports are commonly issued for shorter validity periods "
                "than adult passports. Families should check each child's expiry date "
                "independently rather than assuming they align with a parent's.",
            ]),
            ("9. Platform Limitations", [
                "This demo platform does not verify passport data, does not store identity "
                "documents, and cannot confirm whether a specific passport will be "
                "accepted at a specific border. All passport guidance is advisory.",
            ]),
        ],
    },
    "insurance": {
        "filename": "insurance_policy.md",
        "title": "Travel Insurance Policy (Demo)",
        "category": "protection",
        "destination": "global",
        "sections": [
            ("1. Purpose and Status", [
                f"This document describes the fictional travel-protection product offered "
                f"alongside demo bookings by {COMPANY}. It is not an insurance contract, "
                "not a certificate of cover, and creates no obligations of any kind.",
            ]),
            ("2. Recommended Cover Categories", [
                "For planning purposes the demo itinerary planner assumes a traveller may "
                "wish to hold cover across five categories: emergency medical treatment "
                "and evacuation; trip cancellation and interruption; baggage loss, delay, "
                "and damage; travel delay and missed connection; and personal liability.",
                "Medical and evacuation cover is generally the most consequential "
                "category, particularly for destinations where healthcare must be paid "
                "for upfront.",
            ]),
            ("3. Illustrative Cover Limits", [
                "The demo planner uses these fictional limits when estimating: emergency "
                "medical up to 100,000 USD; emergency evacuation up to 250,000 USD; trip "
                "cancellation up to the insured trip cost; baggage up to 1,500 USD with a "
                "per-item sub-limit; and travel delay of 100 USD per day after a "
                "six-hour delay.",
                "Real products vary enormously. These figures exist only so the demo can "
                "produce a plausible cost line in a budget breakdown.",
            ]),
            ("4. Typical Exclusions (Illustrative)", [
                "Sample exclusions used in this demo include: pre-existing medical "
                "conditions not declared and accepted; injuries arising from extreme "
                "sports or motorcycling without a licence; incidents involving alcohol or "
                "controlled substances; travel undertaken against official advisories; "
                "and losses arising from documentation failures such as an invalid visa.",
                "Cancellation for a change of mind ('disinclination to travel') is "
                "excluded unless a cancel-for-any-reason upgrade has been purchased.",
            ]),
            ("5. When to Purchase", [
                "This demo policy recommends purchasing protection on the same day the "
                "first non-refundable component is paid for. Cancellation cover generally "
                "only responds to events that arise after the policy is in force.",
            ]),
            ("6. Cost Estimation in Itineraries", [
                "When the planner includes an insurance line in a budget, it estimates "
                "roughly four to eight percent of total trip cost for a standard "
                "single-trip product, weighted toward the higher end for travellers over "
                "65 or for destinations with high medical costs. This is a demo heuristic, "
                "not a quotation.",
            ]),
            ("7. Claims Process (Illustrative)", [
                "A sample claims flow: notify the insurer within 30 days of the incident; "
                "submit supporting evidence including receipts, medical reports, and "
                "written confirmation from the airline or hotel; expect assessment within "
                "15 business days; and retain original documents until the claim closes.",
                "Travellers should keep every receipt for expenses they intend to claim, "
                "including for essential purchases during a baggage delay.",
            ]),
            ("8. Interaction with Supplier Refunds", [
                "Where a supplier such as an airline or hotel offers a refund or credit, "
                "insurance generally responds only to the shortfall that remains after "
                "that refund. Travellers should pursue supplier remedies first.",
            ]),
            ("9. No Advice Given", [
                "Neither this document nor the demo agents provide insurance advice or "
                "recommend specific products. Travellers should read the real product "
                "disclosure statement of any policy they consider.",
            ]),
        ],
    },
    "baggage": {
        "filename": "baggage_policy.md",
        "title": "Airline Baggage Policy (Demo)",
        "category": "flights",
        "destination": "global",
        "sections": [
            ("1. Scope", [
                f"This demo baggage policy describes the fictional standards applied by "
                f"the sample carriers in the {COMPANY} demo inventory (Demo Air, "
                "SkyBridge Airlines, Globe Wings, AeroLink, and others). Real airline "
                "allowances differ and must be checked with the operating carrier.",
            ]),
            ("2. Cabin Baggage", [
                "Economy passengers may carry one cabin bag up to 7 kg with maximum "
                "dimensions of 55 x 40 x 20 cm, plus one small personal item such as a "
                "laptop bag or handbag. Premium economy allows 10 kg, and business class "
                "allows two pieces totalling 14 kg.",
                "Cabin bags exceeding these limits at the gate are checked into the hold "
                "for a fee of 65 USD in this demo schedule, and the passenger may not be "
                "able to retrieve items before boarding.",
            ]),
            ("3. Checked Baggage", [
                "The demo economy fare includes one checked bag up to 23 kg. Premium "
                "economy includes two bags up to 23 kg each. Business class includes two "
                "bags up to 32 kg each. Linear dimensions should not exceed 158 cm per "
                "piece.",
                "Additional bags cost 75 USD each when pre-purchased online at least six "
                "hours before departure, or 110 USD each at the airport. Overweight bags "
                "between 23 and 32 kg attract a 90 USD surcharge.",
            ]),
            ("4. Prohibited and Restricted Items", [
                "Lithium batteries above 100 Wh require carrier approval; above 160 Wh "
                "they are not accepted. Spare batteries and power banks must travel in "
                "cabin baggage only, never in the hold.",
                "Sharp items, most tools, flammable liquids, and aerosols beyond personal "
                "care quantities are prohibited in the cabin. Liquids in cabin baggage "
                "must be in containers of 100 ml or less within a single transparent "
                "one-litre bag, subject to local screening rules.",
            ]),
            ("5. Sports and Special Equipment", [
                "Bicycles, golf bags, skis, and surfboards are accepted as a single piece "
                "against the standard allowance where within 23 kg, with an oversize "
                "handling fee of 85 USD in this demo schedule. Musical instruments above "
                "cabin size require an extra seat purchase.",
            ]),
            ("6. Fragile and Valuable Items", [
                "Electronics, jewellery, medication, travel documents, and irreplaceable "
                "items should travel in cabin baggage. Under this demo policy the carrier "
                "accepts no liability for such items placed in checked baggage.",
            ]),
            ("7. Delayed, Damaged, and Lost Baggage", [
                "Report any issue at the arrival airport before leaving the baggage hall "
                "and obtain a property irregularity report. Demo compensation for "
                "essential purchases during a delay is up to 150 USD for the first 24 "
                "hours on production of receipts.",
                "Baggage not located within 21 days is treated as lost. The demo "
                "settlement is calculated on depreciated value up to a ceiling of 1,400 "
                "USD per passenger, and travellers are encouraged to claim the balance "
                "under travel insurance.",
            ]),
            ("8. Connecting Flights and Interline Transfers", [
                "Where an itinerary combines carriers on separate tickets, baggage is not "
                "through-checked and the more restrictive allowance may apply on each "
                "segment. The demo planner flags such itineraries as carrying additional "
                "baggage risk.",
            ]),
            ("9. Verification Requirement", [
                "Because baggage rules change often and vary by route and fare class, the "
                "demo agents always advise confirming the allowance directly with the "
                "operating carrier before travel.",
            ]),
        ],
    },
    "hotel-cancellation": {
        "filename": "hotel_cancellation_policy.md",
        "title": "Hotel Cancellation Policy (Demo)",
        "category": "accommodation",
        "destination": "global",
        "sections": [
            ("1. Scope", [
                f"This demo policy governs cancellation of the mock hotel bookings held in "
                f"the {COMPANY} demo database. No real reservation, payment, or hotel is "
                "involved at any point.",
            ]),
            ("2. Rate Types", [
                "Demo inventory offers three rate types. Flexible rates may be cancelled "
                "free of charge until 18:00 local hotel time on the day before arrival. "
                "Semi-flexible rates may be cancelled free until seven days before "
                "arrival, after which one night is charged. Non-refundable rates are "
                "charged in full from the moment of booking.",
                "Where a rate type is not explicitly stated in the demo record, the "
                "planner assumes semi-flexible terms and says so in its assumptions.",
            ]),
            ("3. Cancellation Fee Schedule", [
                "For semi-flexible bookings the demo schedule is: more than 7 days before "
                "arrival, no fee; 3 to 7 days, one night's charge; 24 to 72 hours, 50 "
                "percent of the total stay; less than 24 hours or no-show, 100 percent of "
                "the total stay.",
            ]),
            ("4. Early Departure", [
                "Guests departing earlier than the confirmed checkout date are charged "
                "for the full original stay under this demo policy unless the booking was "
                "made on a flexible rate, in which case remaining nights are refunded "
                "less one night.",
            ]),
            ("5. Peak Period Exceptions", [
                "During demo-designated peak periods — major festivals, new-year weeks, "
                "and large conventions — a stricter 14-day free-cancellation cut-off "
                "applies and deposits of one to three nights may be non-refundable.",
            ]),
            ("6. Force Majeure and Extenuating Circumstances", [
                "Where travel becomes impossible because of natural disaster, government "
                "border closure, or a documented medical emergency, the demo policy "
                "allows a fee waiver at the property's discretion on production of "
                "supporting evidence. Travel insurance should be the primary remedy.",
            ]),
            ("7. Group Bookings", [
                "Reservations of five or more rooms are treated as group bookings, with a "
                "30-day free-cancellation cut-off and a permitted reduction of up to 10 "
                "percent of rooms without penalty inside that window.",
            ]),
            ("8. How to Cancel in This Demo", [
                "Cancellation in this demo is performed through the operations agent, "
                "which calls the `cancel_booking` MCP tool. The booking's status changes "
                "to `cancelled` and the record is retained for audit — records are never "
                "hard-deleted. No money moves because no payment ever existed.",
            ]),
            ("9. Refund Timing (Illustrative)", [
                "Where a refund would apply in a real deployment, the demo policy quotes "
                "5 to 10 business days back to the original payment method after the "
                "property confirms the cancellation. See the Refund demo policy.",
            ]),
        ],
    },
    "flight-cancellation": {
        "filename": "flight_cancellation_policy.md",
        "title": "Flight Cancellation Policy (Demo)",
        "category": "flights",
        "destination": "global",
        "sections": [
            ("1. Scope", [
                f"This demo policy covers cancellation of the mock flight bookings in the "
                f"{COMPANY} demo inventory, both where the traveller cancels and where the "
                "sample carrier cancels.",
            ]),
            ("2. Traveller-Initiated Cancellation", [
                "Demo fares fall into three families. Saver fares are non-refundable, with "
                "only government taxes returned. Standard fares are refundable less a 120 "
                "USD service fee up to 24 hours before departure. Flex fares are fully "
                "refundable up to two hours before departure.",
                "A 24-hour grace period applies to all fare families: bookings cancelled "
                "within 24 hours of purchase, where departure is at least seven days away, "
                "are refunded in full.",
            ]),
            ("3. Carrier-Initiated Cancellation", [
                "Where a sample carrier cancels a flight, the traveller may choose "
                "rebooking on the next available service at no additional cost, a travel "
                "credit valid 12 months with a 10 percent bonus value, or a full refund of "
                "the unused portion.",
            ]),
            ("4. Significant Schedule Changes", [
                "A schedule change of more than three hours, an added connection, or a "
                "change of departure airport is treated as significant and unlocks the "
                "same three remedies as a cancellation. Smaller changes do not.",
            ]),
            ("5. Delay Compensation (Illustrative)", [
                "The demo schedule offers meal vouchers after a three-hour delay, hotel "
                "accommodation and transfers for an overnight delay within the carrier's "
                "control, and a goodwill credit of 200 USD for delays beyond six hours. "
                "Delays caused by weather, air-traffic control, or security events are "
                "excluded from monetary compensation.",
            ]),
            ("6. Missed Connections", [
                "On a single ticket, the carrier rebooks a missed connection at no cost. "
                "On separate tickets, the traveller bears the cost of the new segment — "
                "the demo planner therefore warns whenever an itinerary relies on a "
                "self-transfer with less than three hours of buffer.",
            ]),
            ("7. No-Show and Onward Segments", [
                "Failing to board a booked segment may cause all onward and return "
                "segments to be cancelled automatically without refund. Travellers who "
                "will not use a segment must cancel it explicitly beforehand.",
            ]),
            ("8. Involuntary Denied Boarding", [
                "Where an oversold flight results in denied boarding, the demo policy "
                "provides rebooking plus compensation of 400 USD for a delay of two to "
                "four hours at destination, and 800 USD beyond four hours.",
            ]),
            ("9. Demo Limitation", [
                "The demo system cannot see live schedules, seat availability, or "
                "disruption status. It never asserts that a flight is currently available "
                "or currently on time; it reports only what the mock database holds.",
            ]),
        ],
    },
    "refund": {
        "filename": "refund_policy.md",
        "title": "Refund Policy (Demo)",
        "category": "payments",
        "destination": "global",
        "sections": [
            ("1. Scope and Nature of Demo Refunds", [
                f"This demo policy explains how refunds would be processed by {COMPANY} in "
                "a production deployment. Because the demo takes no payments, no refund "
                "in this system ever moves real money.",
            ]),
            ("2. Refund Eligibility by Component", [
                "Eligibility is determined by the component's own terms: flights follow "
                "the Flight Cancellation demo policy, hotels follow the Hotel "
                "Cancellation demo policy, and activities are refundable up to 48 hours "
                "before the scheduled start unless marked non-refundable.",
                "Where a package combines components, each is assessed separately and the "
                "traveller receives the sum of the individually refundable amounts.",
            ]),
            ("3. Non-Refundable Elements", [
                "Booking service fees, payment-processing charges, issued travel-insurance "
                "premiums after the cooling-off period, and any visa or permit fees paid "
                "to third parties are non-refundable under this demo policy.",
            ]),
            ("4. Processing Timelines", [
                "Card refunds are quoted at 5 to 10 business days after approval, bank "
                "transfers at 7 to 14 business days, and travel credits are issued within "
                "24 hours. Timelines begin when the supplier confirms cancellation, not "
                "when the traveller submits the request.",
            ]),
            ("5. Partial Refunds and Unused Services", [
                "Unused services within a partly consumed itinerary are refunded at the "
                "component's residual value, not on a pro-rata basis across the whole "
                "package. Discounts allocated across a package may be recalculated.",
            ]),
            ("6. Travel Credits", [
                "Where a credit is issued instead of cash, the demo credit is valid for 12 "
                "months from issue, may be used across multiple bookings, is transferable "
                "to immediate family, and is not exchangeable for cash.",
            ]),
            ("7. Chargebacks", [
                "Travellers are asked to raise a refund request before initiating a card "
                "chargeback. In a production deployment, an open chargeback would pause "
                "parallel refund processing to avoid duplicate credits.",
            ]),
            ("8. Currency and Exchange", [
                "Refunds are returned in the original currency of payment. Where the card "
                "issuer converts, the traveller bears any exchange-rate difference between "
                "the purchase and refund dates.",
            ]),
            ("9. Escalation", [
                "Unresolved refund questions escalate to the fictional demo resolutions "
                "desk with a target first response of two business days. A production "
                "policy would name the regulator or ombudsman available to the traveller.",
            ]),
        ],
    },
    "transportation": {
        "filename": "transportation_policy.md",
        "title": "Ground Transportation Policy (Demo)",
        "category": "transportation",
        "destination": "global",
        "sections": [
            ("1. Purpose", [
                f"This demo policy sets out how {COMPANY} plans and estimates ground "
                "transport within an itinerary, and what the traveller is responsible for.",
            ]),
            ("2. Preferred Modes", [
                "The planner prefers public transport where a city has a reliable network, "
                "on grounds of cost, environmental impact, and predictability in traffic. "
                "Where a city's network is limited, or where travel occurs late at night "
                "or with heavy luggage, licensed taxis or app-based rides are preferred.",
                "Where a destination guide notes a transit pass — for example an IC card, "
                "a daily cap, or a tourist travel card — the planner recommends it and "
                "reflects its cost in the budget.",
            ]),
            ("3. Airport Transfers", [
                "Demo estimates assume a shared shuttle or rail link where available, at "
                "15 to 45 USD per person depending on destination tier, and a private "
                "transfer at 55 to 120 USD per vehicle. Arrivals after 23:00 assume a "
                "private transfer for safety.",
            ]),
            ("4. Intercity Travel", [
                "For journeys under four hours the planner prefers rail where a service "
                "exists, and otherwise a coach. Domestic flights are proposed only where "
                "the surface journey exceeds six hours, to limit both cost and travel "
                "fatigue.",
            ]),
            ("5. Car Rental", [
                "Where a rental is proposed, the demo policy requires the traveller to "
                "hold a licence valid in the destination and, where applicable, an "
                "International Driving Permit. Estimates include basic insurance, fuel, "
                "and a parking allowance. The traveller is responsible for tolls, fines, "
                "and any excess.",
            ]),
            ("6. Daily Transport Budget", [
                "Local transport is estimated at 8 to 20 USD per person per day depending "
                "on destination tier and itinerary spread. Itineraries that concentrate "
                "activities by neighbourhood are estimated at the lower end.",
            ]),
            ("7. Accessibility", [
                "Where a traveller states an accessibility requirement, the planner "
                "prefers step-free routes and accessible vehicles, allows longer transfer "
                "buffers, and flags any proposed venue whose accessibility it cannot "
                "confirm from its knowledge base.",
            ]),
            ("8. Fatigue Management", [
                "The planner limits ground transit to roughly two hours per day on "
                "sightseeing days and avoids scheduling geographically distant activities "
                "on the same day. Long transfers are placed on arrival or departure days "
                "where possible.",
            ]),
            ("9. Safety Notes", [
                "Travellers should use officially marked taxis, confirm the driver and "
                "vehicle against the app before boarding, and consult the destination "
                "guide's safety section for local specifics such as scooter-hire risk.",
            ]),
        ],
    },
    "safety": {
        "filename": "safety_policy.md",
        "title": "Travel Safety Guidelines (Demo)",
        "category": "safety",
        "destination": "global",
        "sections": [
            ("1. Purpose and Limits", [
                f"These demo guidelines describe the general safety posture {COMPANY} "
                "recommends. They are not a security assessment and do not replace "
                "official government travel advisories, which travellers should consult "
                "for their own nationality before departure.",
            ]),
            ("2. Pre-Departure Preparation", [
                "Before travel, register with any available consular notification service, "
                "share the itinerary with a contact at home, save local emergency numbers "
                "offline, keep digital and paper copies of key documents stored "
                "separately, and confirm that insurance covers the planned activities.",
            ]),
            ("3. Health Preparation", [
                "Check recommended vaccinations and any prophylaxis for the destination "
                "well in advance, carry prescription medication in original labelled "
                "packaging with a copy of the prescription, and confirm whether any "
                "medication is restricted at the destination.",
            ]),
            ("4. Personal Property", [
                "Use a hotel safe for documents and valuables, carry only the cash needed "
                "for the day, split payment methods across bags, and stay alert in the "
                "crowded areas each destination guide identifies as pickpocket-prone.",
            ]),
            ("5. Transport Safety", [
                "Prefer licensed transport, verify vehicle details before boarding, wear "
                "seat belts where fitted, and avoid overnight road travel in unfamiliar "
                "regions. Helmet use is expected for any scooter or motorcycle hire.",
            ]),
            ("6. Natural Hazards and Seasonality", [
                "Consult the destination guide's weather section for seasonal hazards such "
                "as typhoon season, monsoon flooding, extreme heat, or high-water events. "
                "Build slack into itineraries planned during a known hazard window.",
            ]),
            ("7. Local Laws and Customs", [
                "Behaviour that is unremarkable at home may be an offence elsewhere. "
                "Travellers should review the local customs section of each destination "
                "guide, particularly regarding dress at religious sites, photography "
                "restrictions, alcohol, and public conduct.",
            ]),
            ("8. In an Emergency", [
                "Contact local emergency services first, then the traveller's embassy or "
                "consulate, then the insurer's 24-hour assistance line. Retain all "
                "documentation, including police reports and medical records, for any "
                "later claim.",
            ]),
            ("9. Solo, Family, and Accessibility Considerations", [
                "Solo travellers are advised to share live location with a trusted contact "
                "and prefer well-reviewed accommodation in central areas. Families should "
                "agree a meeting point at each venue. Travellers with accessibility needs "
                "should confirm venue access directly, since the demo knowledge base may "
                "be incomplete.",
            ]),
        ],
    },
    "booking-modification": {
        "filename": "booking_modification_policy.md",
        "title": "Booking Modification Policy (Demo)",
        "category": "bookings",
        "destination": "global",
        "sections": [
            ("1. Scope", [
                f"This demo policy governs changes to existing mock bookings in the "
                f"{COMPANY} demo database, including dates, travellers, and components.",
            ]),
            ("2. What Can Be Modified", [
                "The demo operations agent can change a booking's item, traveller name, "
                "status, and total cost through the `update_booking` MCP tool. Each change "
                "is written to the SQLite record and is immediately visible on retrieval.",
                "Booking identifiers are never reused or reassigned, and records are never "
                "hard-deleted — a cancellation is recorded as a status change so the audit "
                "trail survives.",
            ]),
            ("3. Change Fees (Illustrative)", [
                "The demo fee schedule is: hotel date change more than 7 days out, no "
                "fee; within 7 days, 25 USD plus any rate difference; flight date change, "
                "80 USD plus fare difference; activity date change more than 48 hours out, "
                "no fee.",
                "Rate and fare differences are always payable by the traveller, and a "
                "lower new rate does not generate a refund of the difference on "
                "non-flexible products.",
            ]),
            ("4. Name Changes", [
                "Correcting a spelling of up to three characters is treated as a "
                "correction and carries no fee. Substituting a different traveller is "
                "treated as a cancellation and rebooking on flights, and as a free "
                "amendment on hotels and activities.",
            ]),
            ("5. Adding and Removing Travellers", [
                "Additional travellers are subject to availability at prevailing demo "
                "rates. Removing a traveller applies the relevant cancellation policy to "
                "that person's share and may change the per-person rate for those who "
                "remain, particularly on twin-share accommodation.",
            ]),
            ("6. Date Changes and Peak Periods", [
                "Moving a booking into a demo peak period incurs the peak rate difference "
                "and the stricter peak cancellation terms described in the Hotel "
                "Cancellation demo policy.",
            ]),
            ("7. Modification Windows", [
                "Modifications are accepted up to 2 hours before a flight, 18:00 local "
                "time the day before a hotel arrival, and 24 hours before an activity. "
                "Later requests are handled as cancellations.",
            ]),
            ("8. How Changes Are Requested in This Demo", [
                "The traveller asks the assistant in natural language — for example "
                "'change my hotel booking' — and the host router delegates to the "
                "operations agent, which classifies the request as `update_booking` and "
                "calls the corresponding MCP tool. The agent will ask for the booking "
                "reference if it was not supplied.",
            ]),
            ("9. Confirmation", [
                "Every successful modification returns the updated record. Travellers "
                "should check that the returned values match what they intended, since "
                "this demo issues no confirmation email.",
            ]),
        ],
    },
}


def main() -> None:
    POLICY_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for topic, spec in POLICIES.items():
        text = _doc(spec["title"], spec["category"], spec["destination"], spec["sections"])
        path = POLICY_DOCS_DIR / spec["filename"]
        path.write_text(text, encoding="utf-8")
        words = len(text.split())
        print(f"  wrote {path.name:<38} topic={topic:<22} ~{words} words")
    print(f"\n{len(POLICIES)} demo policy documents written to {POLICY_DOCS_DIR}")


if __name__ == "__main__":
    main()
