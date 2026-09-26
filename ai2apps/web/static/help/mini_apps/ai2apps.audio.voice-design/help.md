# Characters

Create and manage reusable voice profiles in one library. Select **Create character**, then choose **Design** or **Reference Clone**.

- **Design** opens a voice editor with a description, preview text and a compatible Voice Design model. Click a character card to reopen and edit it. Generate a preview to listen in Preview & Output. Changing the model, description or text requires a new preview.
- **Reference Clone** records or imports reference audio (including Gallery audio), transcribes it, and saves the audio and corrected transcript as a character profile. Saving material does not start model training.

Both methods save to the same character library. Existing profiles and reference audio remain available. Use Back to characters to return to the library.

## Reference materials

Select the voice model first. Its declared sample count, duration limits and transcript requirement appear above the materials. Missing duration declarations remain unknown; the application does not invent quality thresholds. The current upload safety limits are 50 stored clips, 64 MiB of total source audio, and 10 minutes per clip.

Record, upload multiple audio files, or choose Gallery audio. Keep multiple clips in the character and select the subset for the model; single-reference models receive the selected clips merged in list order, subject to the combined duration limit. Audio is stored privately with the character. Choosing Gallery audio copies it into character storage; recordings and uploads are not added to Gallery. Deleting the Gallery original does not affect the character.

Use batch ASR for missing text, or transcribe/retry a single clip. New clips are automatically transcribed when automatic transcription is enabled and ASR is configured. ASR results require review; editing text clears its confirmation. Optional text can be left blank. Preview appears in Preview & Output and uses the selected model and reference audio. Save materials to keep the model revision, all clips, transcripts and selection, then click the character card in the library to reopen them.

Multi-reference execution and actual model training require model-specific adapters that are not currently connected. Those models can save preparation materials but cannot start a fake training or fall back to a different model. Saved materials remain unverified.

## Convert a designed voice

After generating a satisfactory preview, choose a reference-voice model and select **Create Cloned Voice**. This creates a new character and copies that exact preview into character storage as its reference audio, with the generated text ready for review. The original Designed Voice remains available. Review and confirm the reference transcript in Reference Clone before previewing the cloned voice. This fixes a reference voice; it does not fine-tune model weights. The character reference copy survives cleanup of the latest 20 preview outputs.

New designs start with an editable Chinese-and-English preview passage. Use **Use example text** to replace the preview text with that passage. Existing saved text is preserved when reopening a character. Changing preview text clears the selected preview until you regenerate it. The bilingual example helps compare language delivery; it does not guarantee better cloning quality.
