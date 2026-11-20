# IndexTTS 2.5 CUDA notices

Uses fixed IndexTeam IndexTTS 2.5 model weights under the Bilibili Model Use License Agreement. The separate CUDA Runtime supplies pinned WIndexTTS inference modules under Apache-2.0 and AI2Apps inverse-conversion, checkpoint and lifecycle wrappers. Exact upstream source and archive hashes are retained in the Runtime inventory.

The existing fixed FP16 safetensors conversion removes training state and the optional Qwen text-emotion model. Model and implementation license files remain under META/licenses and in the checkpoint distribution. The modified checkpoint and Package are not endorsed, warranted or guaranteed by Bilibili or upstream authors; applicable original right-holder liability disclaimers remain in the bundled terms.

The installing user must accept the exact license or declare applicable separate authorization before checkpoint acquisition. No developer consent is transferred. Numeric emotion and duration controls are supported; independent emotion-reference and text-emotion models are not included.

Development source only: CUDA checkpoint distribution is a draft specification, not signed or published. Runtime publication, model audit and signed installation remain required.
