# South African Agency Procurement

Updated: 2026-08-09

## Operating Position

Market Command does not pretend that South African advertising agencies expose a common campaign API. They do not. Agencies are connected as governed procurement partners:

```text
verified public route
-> DIO campaign hypothesis and proof
-> request-for-quotation package
-> exact Outlook draft or public contact-form package
-> human send/submission
-> quote evidence
-> separate spend-cap approval
-> booking outside DIO
-> provider report
-> DIO lead, order and payment attribution
-> settlement
```

An agency directory entry is discovery evidence only. It is not an endorsement, contact permission, booking, or claim that the agency accepts DIO's present budget.

## Qualified Shortlist

| Partner | DIO pilot fit | Why it is on the shortlist | Primary uncertainty |
| --- | ---: | --- | --- |
| Adclick Africa | 96 | Paid media across budget sizes, social/search/programmatic, tracking and public email route | Actual minimum pilot and fee/media split |
| Plus27 Digital | 95 | Performance channels plus measurement infrastructure; publicly states free consultation and no long contracts | Setup cost at DIO's small starting budget |
| Mark1 | 92 | Integrated media, creative and real-time analytics; publicly includes boutique startups in its client range | Minimum engagement and scope |
| Rogerwilco | 90 | Broad paid media and conversion-oriented capability with a verified public enquiry address | Minimum engagement and management fee |
| AMA Media | 84 | Strong buying, attribution and cross-African capability | Likely scale mismatch at DIO's current stage |
| Entity Y | 83 | Performance and retention expertise across major platforms | Ecommerce evidence may not transfer to bounded professional services |
| Darkstar | 82 | Consultative cross-channel media buying and weekly reporting | Minimum spend and contact route uses a form |
| IntiMedia | 77 | Owner-managed cross-channel positioning that may suit an SME conversation | Digital attribution depth and current minimum |

Incubeta, Ogilvy, Joe Public, Accenture Song, VML, Machine_, Jellyfish, Digitas Liquorice and WPP Media remain benchmark or research routes. Market Command will not prepare outreach for them until route and stage fit are qualified.

## Live Controlled Proof

The first agency connection was prepared for Adclick Africa:

| Object | ID / state |
| --- | --- |
| Campaign | `MKT-B3FB86BF5CB7` / draft, publication held |
| Agency RFQ | `ADCLICK_AFRICA` / Outlook draft ready |
| Media buy | `BUY-76A8EE97F753` / research, approval pending |
| Mail intent | `MAIL-683374577109CC45` / draft, approval pending |
| Quoted amount | `R0.00`, not received |
| Approved cap | `R0.00` |
| Spend policy | `agency_spend=hold` |

The RFQ asks for a minimum viable measurable pilot and requires agency fees, media spend, third-party costs, targeting, dates, creative requirements, cancellation terms and reporting fields to be separated. It explicitly states that the request is not a booking or spend authorisation.

## Operator Workflow

Open `http://127.0.0.1:8770/` and use **South African Media Exchange**.

1. Review the agency's source and current public route.
2. Select **prepare RFQ** and bind it to a DIO campaign.
3. For an email route, inspect the exact draft in Outlook. For a contact-form route, use the generated package on the verified site.
4. Send or submit only after confirming relevance and accuracy.
5. When a response arrives, record the quote and its evidence reference under **Agency Procurement**.
6. Keep the approved cap at zero until the quote, measurement contract, dates and cancellation terms are acceptable.
7. Change `agency_spend` to `release` only for the exact approved buy.
8. After delivery, attach the provider report. Market Command imports reported attention metrics, while DIO remains authoritative for qualified leads, paid orders and verified revenue.

## Sources

- IAB South Africa member discovery: https://iabsa.net/members/
- Adclick Africa paid media: https://adclickafrica.com/paid-media/
- Plus27 Digital: https://plus27digital.com/
- Mark1: https://mark1.co.za/
- Rogerwilco paid media: https://www.rogerwilco.co.za/content-hub/paid-media
- Darkstar: https://darkstarjhb.co.za/
- AMA Media: https://amamedia.co.za/what-we-do/
- Entity Y: https://www.entityy.co.za/
- Incubeta digital media: https://incubeta.com/za/capabilities/digital-media/

All capability descriptions come from the organisations' own public pages and are therefore supplier claims until tested through a quote, references and a bounded pilot.
