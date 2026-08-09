# South African Media Procurement as a DIO Adapter

DIO does not require an API to govern a marketing channel.

A publisher, newsletter, trade site, event, association or agency can be represented through a manual media-buy state machine:

`research -> request for quote -> quote received -> operator review -> spend release -> booking -> publication evidence -> provider report -> DIO attribution -> settlement`

Wave 2 adds an exportable procurement brief. It asks a vendor for inventory, full price, delivery assumptions, creative specifications, targeting, measurement, tracking support and commercial terms.

The brief explicitly states that it is not a booking and that DIO's downstream qualified-lead/order/payment events remain the commercial settlement layer.

This allows local media with no programmable API to be compared against API-native media using the same eventual scoreboard:

- measured spend
- qualified leads
- paid orders
- verified revenue
- cost per qualified lead
- CAC
- verified ROAS

The existing `sa_media_marketplace.json` and `agency_partner_registry.json` remain research registries, not endorsements.
