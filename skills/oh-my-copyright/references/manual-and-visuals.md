# Manual and visuals

The manual must be a real case-relative file and mention the exact software name and version. Record which running version was checked. For visual software, attach real screenshots with feature descriptions; screenshots must exist inside the case directory. A headless tool may declare `ui_type: headless` but still needs a manual and executable evidence.

Use the shared renderer to create DOCX/PDF/page images, then inspect all pages. Source extraction preserves original lines; it never pads, paraphrases, estimates pages or submits registration materials.

Manual Markdown supports headings, paragraphs, literal ordered/unordered list markers (including nested lists), fenced commands, Markdown tables and declared local images. List markers retain their source numbers rather than generating new numeric claims. Raw HTML blocks and inline HTML are rejected with a source line; convert them to Markdown before building. HTML is never silently omitted from the Word document.
