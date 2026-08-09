# DIO Product Work Queue

The Control Deck separates current decisions from historical pipeline runs.

## Work Queue

HOMS and Evidex now use a shared operational envelope with product-specific gates:

```text
intake review
  -> processing
  -> output review where required
  -> governed notification
  -> Outlook draft
  -> manual operator send
```

Only the next valid action is offered. Approval and rejection decisions require explicit confirmation and emit immutable DIO events.

### HOMS

HOMS intake approval authorises preparation of the request pack. The first notification asks for the batch, rubric or memo, assignment context and optional gradebook. It does not claim that marking has occurred. Final marks and feedback still require educator approval in the HOMS production lane.

### Evidex

Evidex intake approval authorises pack processing. Generated evidence packs then require a second output approval before a delivery notification can be prepared. The reviewed ZIP is attached to the Outlook draft only after this gate passes.

## Notifications

Workflow-owned mail intents are represented once in the attention queue under their product. They are not duplicated as separate mail alerts. Once Microsoft Graph creates an Outlook draft, the state becomes `outlook_ready` and the operator is prompted to review it in Outlook.

The system does not send automatically. Initial Graph permission excludes `Mail.Send`.

## Run History

Legacy, dry-run and historical routed jobs remain available under **Run History**. This table is evidence of what ran; it is not the operator action surface.

## Controlled Proof

- HOMS `homs-09d7b6a2e7463661bc81`: intake approved, request pack ready, Outlook upload-request draft created.
- Evidex `evidex-b0a30dd37214755b47d9`: intake approved, output approved, reviewed ZIP attached to an Outlook draft.
- Both drafts target the controlled DIO mailbox because the original fixture senders were redacted.
