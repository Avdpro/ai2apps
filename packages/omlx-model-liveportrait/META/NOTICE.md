# Third-party notices

This Package implements the human LivePortrait pipeline and uses checkpoint
weights converted from `KlingTeam/LivePortrait` revision
`82a4fa6735ca58432b6ce39301b4b9ee066dea47` under the MIT License. The
upstream non-commercial InsightFace models are not included; face detection
and five-point landmarks use the separately MIT-licensed YuNet 2023mar model.

The native MLX architecture modules and GridSample implementation are adapted
from `ivanfioravanti/fasterliveportrait-mlx` commit
`d5361f4806c14fe2051eecb1dd5a89930f46db0d`, under the MIT License. Its full
license text is in `META/licenses/FasterLivePortrait-MLX-MIT.txt`.

YuNet is from OpenCV Zoo commit
`47534e27c9851bb1128ccc0102f1145e27f23f98`. Its directory-specific MIT
license is in `META/licenses/YuNet-MIT.txt`.
