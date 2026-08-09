# Attachment quarantine

Wave 2 accepts a deliberately narrow file set and treats all uploaded bytes as hostile until human review.

DIO validates:
- bounded byte length,
- base64 validity between edge and core,
- SHA-256 consistency,
- allowlisted filename extension,
- MIME/extension compatibility,
- simple file magic for PDF, Office Open XML, PNG and JPEG.

The original user filename is metadata only. Bytes are stored as `content.blob` beneath a random attachment ID. DIO does not use the user filename as an executable filesystem path.

Wave 2 deliberately does **not** claim malware scanning, content safety, macro analysis, archive-bomb analysis, OCR safety, or document-parser isolation. Those belong in a later sanitisation worker before automatic extraction can ever be enabled.
