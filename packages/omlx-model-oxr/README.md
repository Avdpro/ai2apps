# SoMark OXR 1.0 BF16

Requires AI2Apps oMLX Runtime >=1.8.15 and macOS 26.2+ on Apple Silicon.
Document-image OCR only; not a general conversation model. Use temperature=0 and
"Recognize the whole page content of the image." For tables use
"Recognize the table of the image into html format."

Original fixed BF16 checkpoint, no torch remote code execution. The Package does
not contain model weights or the separate layout model. It does not provide a
complete PDF/layout pipeline or automatic Knowledge indexing.

Known limitations: handwritten text/formulas may be incorrect, excessive whitespace
and small text can cause hallucinations after resizing, complex pages can repeat or
hit token limits. Check OCR against the original. Crop margins/regions as appropriate;
this is not a universal accuracy fix. No guarantee of coordinate extraction from
whole-page text output. 16 GiB memory floor is conservative, only M5 Max 128 GiB
has been evaluated. See ai2apps/experiments/oxr_mlx/README.md for evidence.

Uses SoMark OXR. Read LICENSE-OXR before download/use: commercial funding/revenue
thresholds, online-service attribution and competing hosted API restrictions apply.
The download flow requires acceptance of the signed upstream license terms.
