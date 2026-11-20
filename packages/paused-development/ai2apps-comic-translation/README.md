# Comic Translation

Open **Imagine Studio → Comic Translation** and add up to 50 pages using the shared image slots. Select or drop multiple images into the empty slot, including images from Gallery, then reorder the pages before recognizing them. The batch reads all source pages first, then translates each page using the selected model. Neighboring dialogue can be turned off. This Package requires ai2apps/model-oxr >=0.1.0 <1.0.0. Installation resolves its compatible oMLX Runtime dependency. OCR uses the SoMark OXR checkpoint configured on the host.

If OCR is unavailable, select **Install OCR model** in Comic Translation on Desktop. The Studio setup flow checks the Runtime, model package and checkpoint, then refreshes model readiness on return. On Mobile, set up OXR on the host Mac and select **Refresh models**.

In Chat or Bot, attach a comic image and ask for a target language and output format. For example, “Translate this manga page into French and return the finished PNG.” Discover lists the tool under **Comic Translation**, **漫画翻译**, and comic translation tasks. After installation, a compatible AI2Apps Desktop host registers `imagine.translate_comic`. If SoMark OXR is missing, the Desktop conversation shows the installation plan for confirmation.

Automatic cropping proposes a page when it finds a rectangular comic layout. Toggle back to the full screenshot if needed. For vertical originals, select **Vertical (right to left)** to guide recognition and reading order. In narrow, tall boxes, English text rotates clockwise by 90° when it fits appreciably better. Each box also offers manual horizontal or rotated layout. Preview and export report which regions were skipped and preserve the original pixels there. Review the boxes before sharing.

In the editor and translation preview, hover over a detected bubble to see its translation. Expand **Dialogue** to see the original and translated text together. PNG and HTML exports appear in the Studio Output. Download the HTML and open it in a browser. It contains the translated and original pixels for every page. Use the page buttons or arrow keys to navigate, the wheel or pinch to zoom, and drag to pan. Hover over a bubble in the exported reader to see the original, or tap to toggle it on a touch screen.

The editor is a foreground workspace. Complete the batch and export before closing it. Each file can be up to 16 MiB and 24 megapixels. The total export limit is 64 MiB.
