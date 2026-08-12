# DIO Document Studio Conversion Examples

Document format conversion is a byte/layout transformation service, not a semantic editing service. It does not invoke the technical-editing or translation provider pipeline.

## Plan without writing output

```bash
./dio convert-doc report.docx report.pdf --dry-run
```

## Convert text or Markdown to DOCX

```bash
./dio convert-doc notes.md notes.docx
```

## Extract DOCX text

```bash
./dio convert-doc procedure.docx procedure.txt
```

## External converter routes

Office-document conversion may use LibreOffice/soffice, text/document conversion may use Pandoc, and PDF text extraction may use pdftotext. `./dio doctor` reports which route-specific tools are currently available.

Unsupported pairs refuse rather than guessing. Existing outputs are not replaced unless `--force` is explicitly supplied.

Every completed conversion writes an adjacent `.conversion.json` receipt containing the source hash, plan hash, converter identity, output hash, lossiness warnings, and the explicit fact that semantic editing was not performed.
