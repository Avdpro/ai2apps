"""SAM2 video and image predictors. Ported to MLX."""

from typing import Dict, List, Optional, Tuple

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .sam2_base import SAM2Base


def _load_frames(video_path: str, max_frames: int = -1) -> Tuple[np.ndarray, int]:
    """Load video frames using imageio. Returns (frames, fps)."""
    import imageio.v3 as iio

    reader = iio.imiter(video_path)
    frames = []
    fps = 30
    try:
        fps = iio.improps(video_path).fps or 30
    except Exception:
        pass
    for i, frame in enumerate(reader):
        frames.append(frame)
        if max_frames > 0 and i + 1 >= max_frames:
            break
    return np.stack(frames), fps


def _resize_longest_edge(image: np.ndarray, size: int) -> np.ndarray:
    """Resize image so the longest edge equals `size`, keeping aspect ratio."""
    import cv2

    h, w = image.shape[:2]
    scale = size / max(h, w)
    new_h, new_w = int(h * scale), int(w * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def _resize_square(image: np.ndarray, size: int) -> np.ndarray:
    """Resize image to (size, size), DISTORTING aspect ratio.

    PT SAM2 uses torchvision Resize((1024, 1024)) which forces a square
    output; Hiera was trained on these distorted squares. Preserving aspect
    + padding (longest-edge mode) gives Hiera input geometry it has never
    seen, and on low-contrast frames it produces full-frame noise masks.
    """
    import cv2

    return cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)


def _pad_to_size(image: np.ndarray, size: int) -> np.ndarray:
    """Pad image to square `size × size`."""
    h, w = image.shape[:2]
    pad_h = size - h
    pad_w = size - w
    if image.ndim == 3:
        return np.pad(image, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant")
    else:
        return np.pad(image, ((0, pad_h), (0, pad_w)), mode="constant")


class SAM2VideoPredictor(nn.Module):
    """SAM2 video predictor — tracks masks across video frames."""

    def __init__(self, model: SAM2Base):
        super().__init__()
        self.model = model
        self.image_size = model.image_size
        self._images = None
        self._features = {}
        self._mask_inputs_per_obj = {}
        self._obj_id_to_idx = {}
        self._is_init_cond_frame = {}
        self._consolidated = False
        self._non_cond_frame_outputs: Dict[int, dict] = {}
        self._cond_frame_outputs: Dict[int, dict] = {}
        self._output_dict: Dict[int, dict] = {}

    def init_state(
        self,
        video: np.ndarray,
        offload_video_to_cpu: bool = True,
        preload_features: bool = True,
        progress_callback=None,
    ):
        """Initialize tracking state from video frames.

        Args:
            video: [F, H, W, C] numpy array in [0, 255] or [0, 1]
            preload_features: if True, run Hiera + neck on every frame
                during init so propagation only does memory + mask_decoder
                (much faster track). Matches the official SAM2 web-demo
                UX: "first click pause, then instant track".
            progress_callback: fn(done, total) called after each frame's
                feature extraction so the caller can surface progress.
        """
        frames = []
        original_sizes = []
        for i in range(len(video)):
            img = video[i]
            if img.max() > 1.0:
                img = img.astype(np.float32) / 255.0
            else:
                img = img.astype(np.float32)
            original_sizes.append(img.shape[:2])
            # Square resize to match PT SAM2 training-time geometry
            img = _resize_square(img, self.image_size)
            frames.append(img)
            mx.eval(mx.array(0))  # periodic eval to free memory

        self._images = np.stack(frames)  # [F, H, W, C]
        self._original_sizes = original_sizes
        self._num_frames = len(frames)
        self._obj_id_to_idx = {}
        self._mask_inputs_per_obj = {}
        self._is_init_cond_frame = {}
        self._consolidated = False
        self._non_cond_frame_outputs = {}
        self._cond_frame_outputs = {}
        self._output_dict = {}

        # Pre-extract Hiera + FPN + conv_s0/s1 features for every frame.
        # This is the dominant cost in track (~250 ms/frame on Apple Silicon
        # for Hiera-Large), so doing it once up-front turns propagate into
        # a memory-attention + mask-decoder loop (~80 ms/frame), matching
        # the SAM2 official demo behavior: long pause on first click, then
        # near-instant tracking.
        n = len(frames)
        if preload_features:
            for i in range(n):
                img_chw = np.array(frames[i]).transpose(2, 0, 1)
                img_chw = _imagenet_normalize_chw(img_chw)
                feats = self.model.forward_image(mx.array(img_chw)[None])
                # Force eager evaluation so memory is freed and the next
                # iteration starts from a clean slate. Without this MLX
                # would queue all 54 frames' work and fire it lazily,
                # which spikes memory and confuses progress reporting.
                mx.eval(*feats.values())
                self._features[i] = feats
                if progress_callback is not None:
                    progress_callback(i + 1, n)
        else:
            # Backward-compat: just frame 0 (original behavior).
            img0 = np.array(frames[0]).transpose(2, 0, 1)
            img0 = _imagenet_normalize_chw(img0)
            img0 = mx.array(img0)[None]
            self._features[0] = self.model.forward_image(img0)

    def add_new_points(
        self,
        frame_idx: int,
        obj_id: int,
        points: np.ndarray,
        labels: np.ndarray,
        clear_old_points: bool = True,
    ):
        """Add click points for an object at a specific frame."""
        if obj_id not in self._obj_id_to_idx:
            self._obj_id_to_idx[obj_id] = len(self._obj_id_to_idx)
            self._mask_inputs_per_obj[obj_id] = None
            self._is_init_cond_frame[obj_id] = True

        if frame_idx not in self._features:
            img = np.array(self._images[frame_idx]).transpose(2, 0, 1)
            img = _imagenet_normalize_chw(img)
            img = mx.array(img)[None]
            self._features[frame_idx] = self.model.forward_image(img)

        # Scale points from original-frame pixel space → 1024 model input space.
        # PromptEncoder divides by input_image_size (=1024) to normalize, so the
        # points must already be in 1024-px coordinates. Without this, clicks
        # in (1280, 720) video at e.g. (640, 360) became (640, 360) / 1024 ≈
        # (0.625, 0.35) but should have been (1024 * 640/1280, 1024 * 360/720) /
        # 1024 = (0.5, 0.5).
        orig_h, orig_w = self._original_sizes[frame_idx]
        sx = self.image_size / orig_w
        sy = self.image_size / orig_h
        scaled = np.array(points, dtype=np.float32).copy()
        scaled[:, 0] = scaled[:, 0] * sx
        scaled[:, 1] = scaled[:, 1] * sy

        # Run single-frame inference
        output = self._run_single_frame(
            frame_idx,
            obj_id,
            points=scaled,
            labels=np.array(labels, dtype=np.int32),
            run_mem_encoder=False,
        )
        return output

    def refine_init_with_click_cc(
        self,
        frame_idx: int,
        obj_id: int,
        points: np.ndarray,
        labels: np.ndarray,
    ) -> int:
        """Override the candidate stored in `_cond_frame_outputs[frame_idx]`
        to use the click-containing connected component instead of
        SAM2's argmax(iou_pred) choice.

        SAM2 with multiple positive clicks on a SMALL object (e.g. Jerry
        in cartoon/4.mp4) can rank a LARGER nearby object higher by IoU,
        so the default argmax pick stores the wrong mask in memory and
        propagation drifts onto that other object. The user's clicks are
        an explicit "this is what I want" signal — when their CC is
        non-empty in any candidate, that candidate is the one we should
        memorise.

        Returns the candidate index actually picked (0..2) or -1 if no
        click-containing CC was found in any candidate (in which case
        the existing SAM2-iou choice is left in place).
        """
        out = self._output_dict.get(frame_idx, {}).get(obj_id)
        if out is None:
            return -1

        masks = np.array(out["pred_masks_high_res"][0])  # [3, H_m, W_m]
        # Resize per-axis to the original frame; clicks are in original-px
        # space, so we do CC analysis in the same coordinate frame the
        # user clicked in.
        orig_h, orig_w = self._original_sizes[frame_idx]
        import cv2
        resized = []
        for i in range(masks.shape[0]):
            resized.append(
                cv2.resize(masks[i], (orig_w, orig_h),
                           interpolation=cv2.INTER_LINEAR)
            )
        masks_full = np.stack(resized, axis=0)

        # First positive click as the anchor. (If no positives, fall back
        # to the first click regardless.)
        anchor = None
        for px, py, lab in zip(points[:, 0], points[:, 1], labels):
            if int(lab) == 1:
                anchor = (float(px), float(py))
                break
        if anchor is None:
            anchor = (float(points[0, 0]), float(points[0, 1]))

        cx = max(0, min(orig_w - 1, int(round(anchor[0]))))
        cy = max(0, min(orig_h - 1, int(round(anchor[1]))))

        max_cover_px = int(0.5 * orig_h * orig_w)
        # Score each candidate: must contain ALL positive clicks; among
        # those, the SMALLEST area is the tightest fit (large candidates
        # bleed into nearby objects, e.g. Jerry+Tom both included).
        pos_xy = [
            (max(0, min(orig_w - 1, int(round(px)))),
             max(0, min(orig_h - 1, int(round(py)))))
            for px, py, lab in zip(points[:, 0], points[:, 1], labels) if int(lab) == 1
        ]
        if not pos_xy:
            return -1

        best_size = None  # smallest acceptable
        best_idx = -1
        for i in range(masks_full.shape[0]):
            lg = np.clip(masks_full[i], -30.0, 30.0)
            sigm = 1.0 / (1.0 + np.exp(-lg))
            binary = (sigm > 0.5).astype(np.uint8)
            total_pos = int(binary.sum())
            if total_pos > max_cover_px or total_pos == 0:
                continue
            n_labels, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(
                binary, connectivity=4
            )
            # Find the (single) CC that contains ALL positive clicks. If
            # different clicks land in different CCs, this candidate is
            # too fragmented — skip.
            click_cc = set()
            ok = True
            for cx, cy in pos_xy:
                cl = int(labels_cc[cy, cx])
                if cl == 0:
                    ok = False
                    break
                click_cc.add(cl)
            if not ok or len(click_cc) != 1:
                continue
            cl = next(iter(click_cc))
            sz = int(stats_cc[cl, cv2.CC_STAT_AREA])
            if best_size is None or sz < best_size:
                best_size = sz
                best_idx = i

        if best_idx < 0:
            return -1

        # Build a mask that contains ONLY the click-CC blob from the
        # chosen candidate. Other CCs in the same candidate (e.g. Tom in
        # the Jerry-targeted scene) get zeroed so memory propagation
        # doesn't latch onto them.
        chosen_full = masks_full[best_idx]                    # [H, W] logits
        sigm = 1.0 / (1.0 + np.exp(-np.clip(chosen_full, -30, 30)))
        binary = (sigm > 0.5).astype(np.uint8)
        n_labels, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=4
        )
        # Find click-containing CC (we already verified all clicks are in
        # the same CC during scoring).
        cl = int(labels_cc[pos_xy[0][1], pos_xy[0][0]])
        only_click_blob = (labels_cc == cl).astype(np.float32)

        # Convert the click-blob binary back to logits at the model
        # resolution. The original cached mask is at [B=1, 3, H_m, W_m]
        # in model-input space (1024/4 = 256 typically). Resize the
        # blob, scale into logit space (>0 inside blob, <<0 outside).
        H_m, W_m = out["pred_masks_high_res"].shape[2:]
        blob_resized = cv2.resize(only_click_blob, (W_m, H_m),
                                  interpolation=cv2.INTER_LINEAR)
        new_logits = (blob_resized * 20.0 - 10.0).astype(np.float32)  # ~ +10/-10
        new_logits_mx = mx.array(new_logits).reshape(1, 1, H_m, W_m)
        m_repeat = mx.broadcast_to(new_logits_mx, (1, 3, H_m, W_m))
        out["pred_masks_high_res"] = m_repeat

        # Re-run memory encoder on the click-blob mask so cond_frame_outputs
        # carries the right object representation through propagation.
        feats = self._features[frame_idx]
        vision_feats, _, feat_sizes = self.model._prepare_backbone_features(feats)
        mem_feat, mem_pos = self.model._encode_new_memory(
            vision_feats, feat_sizes, m_repeat,
            is_mask_from_pts=True,
            iou_pred=mx.array([[1.0, 1.0, 1.0]]),
        )
        self._cond_frame_outputs[frame_idx] = {
            "maskmem_features": mem_feat,
            "maskmem_pos_enc": mem_pos,
            "obj_ptr": out["obj_ptr"],
        }
        self._output_dict[frame_idx][obj_id] = out
        return best_idx

    def _run_single_frame(
        self,
        frame_idx: int,
        obj_id: int,
        points: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
        run_mem_encoder: bool = True,
    ) -> dict:
        """Run SAM2 on a single frame."""
        feats = self._features[frame_idx]
        bb_feats = feats["backbone_fpn"]
        pos_enc = feats["vision_pos_enc"]

        # Prepare backbone features
        vision_feats, vision_pos_embeds, feat_sizes = self.model._prepare_backbone_features(feats)

        # Prepare point inputs
        point_inputs = None
        if points is not None and labels is not None:
            point_inputs = (
                mx.array(points).reshape(1, -1, 2),
                mx.array(labels).reshape(1, -1),
            )

        mask_input = self._mask_inputs_per_obj.get(obj_id)

        # High-res features
        s0 = feats.get("high_res_feats_s0")
        s1 = feats.get("high_res_feats_s1")

        output = self.model.track_step(
            frame_idx=frame_idx,
            is_init_cond_frame=self._is_init_cond_frame.get(obj_id, True),
            current_vision_feats=vision_feats,
            current_vision_pos_embeds=vision_pos_embeds,
            feat_sizes=feat_sizes,
            point_inputs=point_inputs,
            mask_inputs=mask_input,
            high_res_feats_s0=s0,
            high_res_feats_s1=s1,
            cond_frame_outputs=self._cond_frame_outputs,
            non_cond_frame_outputs=self._non_cond_frame_outputs,
        )

        # Store results
        self._output_dict[frame_idx] = self._output_dict.get(frame_idx, {})
        self._output_dict[frame_idx][obj_id] = output

        if run_mem_encoder:
            self._is_init_cond_frame[obj_id] = False
            # Only add to non-cond if not already a conditioning frame.
            # Cond frames (from add_new_points) stay in _cond_frame_outputs
            # with t_pos=0 temporal encoding (matches PT behavior).
            if frame_idx not in self._cond_frame_outputs:
                self._non_cond_frame_outputs[frame_idx] = {
                    "maskmem_features": output["maskmem_features"],
                    "maskmem_pos_enc": output["maskmem_pos_enc"],
                    "obj_ptr": output["obj_ptr"],
                }
        else:
            # Store as temporary conditioning
            self._cond_frame_outputs[frame_idx] = {
                "maskmem_features": output["maskmem_features"],
                "maskmem_pos_enc": output["maskmem_pos_enc"],
                "obj_ptr": output["obj_ptr"],
            }
            self._is_init_cond_frame[obj_id] = False

        return output

    def propagate_in_video(self, start_frame: int = 0, max_frames: int = -1):
        """Propagate masks through the video, yielding per-frame results.

        Yields:
            (frame_idx, obj_ids, video_res_masks) — masks at original video resolution
        """
        num_frames = self._num_frames
        if max_frames > 0:
            num_frames = min(start_frame + max_frames, num_frames)

        # Pre-flight: consolidate conditioning frames
        self._consolidate_cond_frames(start_frame)

        for frame_idx in range(start_frame, num_frames):
            if frame_idx in self._output_dict:
                masks, ious = self._get_video_res_masks(frame_idx)
                yield frame_idx, list(self._obj_id_to_idx.keys()), masks, ious
                continue

            if frame_idx not in self._features:
                img = np.array(self._images[frame_idx]).transpose(2, 0, 1)
                img = _imagenet_normalize_chw(img)
                img = mx.array(img)[None]
                self._features[frame_idx] = self.model.forward_image(img)

            for obj_id in self._obj_id_to_idx:
                self._run_single_frame(frame_idx, obj_id, run_mem_encoder=True)

            masks, ious = self._get_video_res_masks(frame_idx)
            yield frame_idx, list(self._obj_id_to_idx.keys()), masks, ious

    def _consolidate_cond_frames(self, start_frame: int):
        """Keep conditioning frames in cond_frame_outputs (PT behavior).

        PT keeps cond frames with t_pos=0 temporal encoding throughout
        propagation. Previously this method moved them to non_cond_frame_outputs
        with t_pos=num_maskmem-1, which gave the prompt frame the wrong temporal
        position encoding and caused object_score_logits to go negative on
        subsequent frames.
        """
        if self._consolidated:
            return
        # Cond frames are already stored in _cond_frame_outputs by
        # _run_single_frame(run_mem_encoder=False). Just ensure they have
        # the memory features (they do — track_step always encodes memory).
        self._consolidated = True

    def _get_video_res_masks(self, frame_idx: int):
        """Returns (masks_logits, iou_pred) for ALL objs at this frame.

        masks_logits: [N_obj, 3, H_orig, W_orig] raw logits, one per
                      multimask candidate, bilinearly resized to original
                      video resolution.
        iou_pred:     [N_obj, 3] SAM2's own quality estimate per candidate.

        Critical for tracking: use `argmax(iou_pred[obj_idx])` to pick the
        candidate SAM2 thinks best matches the prompt. Falling back to a
        "largest CC" heuristic when the click drifts off the object causes
        the tracker to silently switch to whichever larger object is
        nearby (e.g. Jerry → Tom on the cartoon test video).
        """
        orig_h, orig_w = self._original_sizes[frame_idx]

        all_masks = []
        all_ious = []
        for obj_id in self._obj_id_to_idx:
            out = self._output_dict.get(frame_idx, {}).get(obj_id)
            if out is None:
                all_masks.append(np.full((3, orig_h, orig_w), -20.0, dtype=np.float32))
                all_ious.append(np.zeros((3,), dtype=np.float32))
                continue
            logits = np.array(out["pred_masks_high_res"][0])  # [3, H_m, W_m]
            ious = np.array(out.get("iou_pred", np.zeros((1, 3)))).reshape(-1)
            if ious.size != 3:  # in case shape was [B, M] with B=1, M=3
                ious = ious.reshape(-1)[:3]
            import cv2
            resized = []
            for c in range(logits.shape[0]):
                resized.append(
                    cv2.resize(logits[c], (orig_w, orig_h),
                               interpolation=cv2.INTER_LINEAR)
                )
            all_masks.append(np.stack(resized, axis=0).astype(np.float32))
            all_ious.append(ious.astype(np.float32))
        return (np.stack(all_masks, axis=0),                   # [N_obj, 3, H, W]
                np.stack(all_ious, axis=0))                    # [N_obj, 3]


# SAM2 was trained with ImageNet normalization on the image encoder. Feeding
# `(img * 2 - 1)` (which maps [0, 1] → [-1, 1] uniformly) gives Hiera input
# statistics that don't match training, producing scattered feature noise on
# real video frames. Use the same per-channel mean/std the PT predictor uses.
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _imagenet_normalize_chw(img_chw: np.ndarray) -> np.ndarray:
    """img_chw: [3, H, W] floats in [0, 1] — return same shape, normalized."""
    mean = _IMAGENET_MEAN.reshape(3, 1, 1)
    std = _IMAGENET_STD.reshape(3, 1, 1)
    return (img_chw - mean) / std


class SAM2ImagePredictor(nn.Module):
    """SAM2 single-image predictor."""

    def __init__(self, model: SAM2Base):
        super().__init__()
        self.model = model
        self._features = None

    def set_image(self, image: np.ndarray):
        """Set the current image. image: [H, W, C] in [0, 255] or [0, 1]."""
        img = image.astype(np.float32)
        if img.max() > 1.0:
            img = img / 255.0
        # PT SAM2: square resize (no padding, distorts aspect). Required to
        # match training-time geometry; longest-edge + pad gave Hiera unseen
        # input layout and produced scattered full-frame masks on low-contrast
        # real video frames.
        img = _resize_square(img, self.model.image_size)
        img = img.transpose(2, 0, 1)  # [C, H, W]
        img = _imagenet_normalize_chw(img)
        img = mx.array(img)[None]  # [1, 3, H, W]
        self._features = self.model.forward_image(img)
        self._original_size = image.shape[:2]

    def predict(
        self,
        point_coords: Optional[np.ndarray] = None,
        point_labels: Optional[np.ndarray] = None,
        multimask_output: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Predict masks for the current image."""
        import cv2

        feats = self._features
        bb_feats = feats["vision_features"]

        # Prepare backbone features
        vision_feats, vision_pos_embeds, feat_sizes = self.model._prepare_backbone_features(feats)

        point_inputs = None
        if point_coords is not None and point_labels is not None:
            # PT SAM2 distorts to a square at image_size; coords scale per-axis,
            # not by max(h,w). Old longest-edge code used a single uniform scale
            # which mis-positioned clicks horizontally on portrait video and
            # vertically on landscape video.
            orig_h, orig_w = self._original_size
            sx = self.model.image_size / orig_w
            sy = self.model.image_size / orig_h
            coords = point_coords.astype(np.float32).copy()
            coords[:, 0] = coords[:, 0] * sx
            coords[:, 1] = coords[:, 1] * sy
            point_inputs = (
                mx.array(coords).reshape(1, -1, 2),
                mx.array(point_labels).reshape(1, -1),
            )

        output = self.model.track_step(
            frame_idx=0,
            is_init_cond_frame=True,
            current_vision_feats=vision_feats,
            current_vision_pos_embeds=vision_pos_embeds,
            feat_sizes=feat_sizes,
            point_inputs=point_inputs,
            high_res_feats_s0=feats.get("high_res_feats_s0"),
            high_res_feats_s1=feats.get("high_res_feats_s1"),
        )

        masks = np.array(output["pred_masks_high_res"][0])
        iou = np.array(output.get("iou_pred", mx.zeros((1, 3)))[0])
        obj_ptr = np.array(output["obj_ptr"])

        # The mask is at (image_size/4) in square space. Since we square-resize
        # without padding, the entire mask grid maps to the original image —
        # no padding crop needed; just resize per-axis back.
        orig_h, orig_w = self._original_size
        resized = []
        for i in range(masks.shape[0]):
            m = cv2.resize(masks[i], (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            resized.append(m)
        masks = np.stack(resized)

        return masks, iou, obj_ptr
