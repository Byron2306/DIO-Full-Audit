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
