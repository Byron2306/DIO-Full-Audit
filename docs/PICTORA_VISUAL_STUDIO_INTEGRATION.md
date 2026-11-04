# Pictora visual studio integration

Pictora now supplies local image candidates to DIO review surfaces through
`products/pictora_visual_studio.py`. The helper copies a local asset beside the
HTML that uses it, adds a responsive decorative figure with a visible review
caption, and writes a SHA-256 provenance receipt. It never changes the semantic
source, factual evidence, or image alt-text authority.

## Connected paths

- HOMS Learning Studio selects an existing Pictora illustration by subject,
  places it in the learning bundle's HTML preview, and uses it as the video
  preview poster when a matching video is present. The rendered video and its
  rights/approval records are unchanged.
- Format Core HTML review outputs can include the DIO Pictora visual candidate
  for Document Studio and Format Studio products. Release-mode output is not
  decorated. Correspondence attaches its candidate after copying the HTML into
  the customer review folder so the image stays local to the deliverable.
- Accessible Publish adds the visual as decorative-only (`alt=""`); its QA
  record still requires descriptions for source figures and makes no formal
  WCAG/PDF-UA certification claim.
- Site Studio includes the image in the held full-grade site proof, alongside
  its governed Format Core scene visuals.
- Market Command's campaign lab may select the Pictora image as a local frame
  source for NicheFoundry media. Its receipt identifies the candidate and keeps
  visual review and campaign release held.

## Review and commercial gate

Pictora's local ComfyUI receipts currently mark commercial validation
`UNPROVED`. The integration therefore records generated images as review
candidates, does not mark them commercially selectable in Format Core's
registry, and does not grant publication, email-send, educator, or campaign
release authority. Confirm the checkpoint and adapter terms, then approve the
specific assets before commercial use.

The correspondence image is part of the HTML review surface. It does not alter
the plain-text companion or the separate human-held send action. Customer email
templates should embed the reviewed asset through their own inline/CID route if
they need to display it inside an email client.
