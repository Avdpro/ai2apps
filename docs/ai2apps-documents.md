# AI2Apps Documents

AI2Apps treats uploaded files as durable, Session-scoped Attachments. File
bytes are content-addressed by SHA-256, while access remains isolated to the
Session that owns each Attachment ID. Parsing runs in the background and
unfinished jobs are recovered after restart.

## Read formats

- PDF (extractable text; scanned/image-only PDF reports that OCR is required)
- DOCX and PPTX
- XLSX and CSV
- TXT, Markdown, JSON, HTML, and HTM

Parsed blocks retain source coordinates when available: PDF page, PowerPoint
slide, spreadsheet sheet/cell range, and document section.

Agents can use `attachment.list`, `attachment.status`, `document.info`,
`document.preview`, `document.read`, and `document.search`.

## PDF generation

`document.create_pdf` converts bounded Markdown or plain text into a PDF in the
Session workspace and registers the result as an immutable Artifact. It
supports headings, paragraphs, bullet lists, fenced code, Markdown tables,
explicit page breaks (`---`), links, A4/Letter pages, multilingual text,
headers, footers, and page numbers.

Every generated PDF is reopened with pypdf to verify page structure and
extractable content. When Poppler is available, every page is also rendered to
PNG before the Artifact is published. The Tool requires both `workspace.write`
and `artifact.create` capabilities.

Text formats such as Markdown, JSON, CSV, HTML, and source code can also be
created through `workspace.write` and promoted through `artifact.create`.
Dedicated DOCX, PPTX, and XLSX generation Tools are not part of this version.
