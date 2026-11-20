# EchoMimic V3 CUDA

This Package supplies the AI2Apps CUDA Worker adapter. The required CUDA Runtime retains the pinned official EchoMimic implementation, source archive, LICENSE.txt, LEGAL.md, and AI2Apps media, recovery and checkpoint-layout wrappers. Source and checkpoint versions are pinned in service.yaml and the Runtime inventory.

The fixed converted checkpoint combines EchoMimicV3, Wan-Fun, UMT5 and AI2Apps conversion under Apache-2.0, and Chinese Wav2Vec2 Base under MIT. Its COMPOSITE-LICENSE.txt, LICENSE and NOTICE remain part of the checkpoint distribution. Weights and Runtime binaries are not included in this Package.

Development contract only. The signed CUDA distribution candidate is not yet published; Runtime publication, installation audit, shared Runtime GPU and signed installation acceptance remain required. Fast mode supports one window; segmented long mode requires exact. Mac numerical precision and performance are not claimed as CUDA guarantees.
