# Microsoft Outlook + OneDrive Route

Updated: 2026-08-07

## Why This Route Exists

The Google Form route proved that intake emails and upload/job folders can be created, but this product wants Outlook as the primary commercial mailer. The cleaner production spine is therefore Microsoft-first:

```text
Outlook lead or reply
-> qualified by triage
-> OneDrive/SharePoint upload folder
-> local mirror folder
-> product watcher or runner
-> review pack
-> Outlook delivery
```

## Local Folder Contract

Create or sync this root:

```text
/home/byron/KnowEdge_Microsoft_Mirror
```

Each product gets the same operational folders:

```text
EVIDEX/
  incoming/
  processing/
  done/
  failed/
  deliveries/

HOMS/
  incoming/
  processing/
  done/
  failed/
  deliveries/
```

## Evidex Path

```text
Outlook ad/reply
-> intake email with OneDrive upload link
-> Evidence files land in EVIDEX/incoming/<job>/uploads
-> intake.yaml lands beside uploads/
-> Evidex watcher processes the local mirror
-> output ZIP goes to EVIDEX/done/<job>
-> Outlook sends delivery
```

Ready condition:

```text
intake.yaml exists
uploads/ contains at least one source file
```

## HOMS Path

```text
Outlook HOMS lead
-> educator sends fake/redacted/non-sensitive batch, rubric, memo, marksheet
-> files land in HOMS/incoming/<job>/uploads
-> HOMS batch runner generates draft marking support
-> educator reviews and approves
-> Outlook sends the review pack
```

Ready condition:

```text
rubric or memo exists
at least one submission exists
educator-review boundary is explicit
```

## Windows Setup

On the Windows/NWU machine, use normal OneDrive sync and select a folder named:

```text
KnowEdge_Microsoft_Mirror
```

Then mirror/sync the product folders above. The local watchers should point to the product root, not the cloud URL.

## Linux Setup

This laptop does not currently have `onedrive` or `rclone` installed/running. For Linux, mount OneDrive with `rclone` or a OneDrive client and map the synced root to:

```text
/home/byron/KnowEdge_Microsoft_Mirror
```

The AutoRelease config for this route is:

```text
config/microsoft_mirror_routes.json
```

## Boundary

HOMS and Evidex outputs remain operator-reviewed. HOMS must use fake, redacted, or non-sensitive learner data until the governance and client approval posture is explicit.
# Outlook outbound recovery note (2026-11-04)

The Graph send path now treats transport exceptions as `in_doubt`, consumes the
one-use approval, and blocks reapproval while provider state is unresolved. This
avoids retrying a send that Graph may already have accepted. A successful Graph
send response is recorded as `accepted_by_graph`; the receipt explicitly says
delivery is not yet confirmed and requires reconciliation. Graph's send-draft
endpoint returns `202 Accepted` with no body, which signals acceptance, not
completed delivery. The immutable draft ID can be used to look for the sent
copy, but that copy may not appear immediately. See Microsoft's
[send-draft response contract](https://learn.microsoft.com/en-us/graph/api/message-send?view=graph-rest-1.0)
and [immutable ID guidance](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).

The reconciliation operation itself and controlled-mailbox proof are still
pending. `in_doubt` intents must not be resent from the UI or by direct script
invocation. Legacy `failed` intents are also held because the older state did
not distinguish a definite rejection from a lost response.
