# Public identity binding

Presence identifiers prove only that a message came from a channel identity. They do **not** prove that the sender owns a DIO order.

Wave 2 therefore uses explicit operator-created bindings.

## Flow

1. Public conversation exists.
2. User requests order/payment/job status.
3. DIO finds no binding and creates `Needs You`.
4. Operator verifies the customer/order relationship through an appropriate independent method.
5. Operator binds exact conversation ID to exact local order ID(s).
6. Later status requests expose minimal state for those order IDs only.
7. Binding can be revoked immediately.

## API

Requires `Authorization: Bearer $DIO_PRESENCE_OPERATOR_TOKEN`.

`POST /api/presence/identity-bindings`

```json
{
  "conversation_id": "CONV-...",
  "order_ids": ["DIO-ORDER-001"],
  "verification_method": "matched customer against payment receipt"
}
```

`DELETE /api/presence/identity-bindings/{conversation_id}` revokes it.

A binding is a disclosure capability, not ownership truth beyond the operator's verification statement. DIO records the method and verifier so the decision is auditable.
