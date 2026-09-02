"""Pinned Flow UniPC scheduler for the eight-step EchoMimicV3 Flash path."""

from __future__ import annotations

from dataclasses import dataclass

import mlx.core as mx
import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class FlowUniPCConfiguration:
    """The fixed second-order upstream scheduler settings used by M2."""

    num_train_timesteps: int = 1000
    solver_order: int = 2
    prediction_type: str = "flow_prediction"
    predict_x0: bool = True
    solver_type: str = "bh2"
    lower_order_final: bool = True
    final_sigmas_type: str = "zero"

    def __post_init__(self) -> None:
        if self.num_train_timesteps <= 0:
            raise ValueError("training timestep count must be positive")
        if self.solver_order != 2:
            raise ValueError("the pinned Flow UniPC path requires solver order 2")
        if self.prediction_type != "flow_prediction" or not self.predict_x0:
            raise ValueError("the pinned scheduler requires x0 flow prediction")
        if self.solver_type != "bh2" or self.final_sigmas_type != "zero":
            raise ValueError("the pinned scheduler requires bh2 with a zero final sigma")


class FlowUniPCScheduler:
    """Stateful MLX translation of the pinned upstream Flow UniPC implementation."""

    def __init__(self, configuration: FlowUniPCConfiguration | None = None) -> None:
        self.configuration = configuration or FlowUniPCConfiguration()
        self.timesteps: npt.NDArray[np.int64] = np.empty((0,), dtype=np.int64)
        self.sigmas: npt.NDArray[np.float32] = np.empty((0,), dtype=np.float32)
        self.model_outputs: list[mx.array | None] = [None, None]
        self.timestep_list: list[int | None] = [None, None]
        self.lower_order_nums = 0
        self.last_sample: mx.array | None = None
        self.step_index: int | None = None
        self.this_order = 0

    def set_timesteps(self, num_inference_steps: int = 8, *, shift: float = 5.0) -> None:
        """Build the exact shifted linear sigma schedule used by the fixed run."""

        if num_inference_steps <= 0 or shift <= 0:
            raise ValueError("inference step count and shift must be positive")
        training = self.configuration.num_train_timesteps
        alphas = np.linspace(1, 1 / training, training, dtype=np.float64)[::-1].copy()
        training_sigmas = (1.0 - alphas).astype(np.float32)
        values = np.linspace(training_sigmas[0], training_sigmas[-1], num_inference_steps + 1)[:-1]
        values = shift * values / (1 + (shift - 1) * values)
        self.timesteps = (values * training).astype(np.int64)
        self.sigmas = np.concatenate([values, [0.0]]).astype(np.float32)
        self.model_outputs = [None, None]
        self.timestep_list = [None, None]
        self.lower_order_nums = 0
        self.last_sample = None
        self.step_index = None
        self.this_order = 0

    def _initialize_step_index(self, timestep: int) -> None:
        indices = np.flatnonzero(self.timesteps == timestep)
        if not len(indices):
            raise ValueError(f"timestep {timestep} is not in the active schedule")
        self.step_index = int(indices[1] if len(indices) > 1 else indices[0])

    @staticmethod
    def _lambda(sigma: np.float32) -> np.float32:
        return np.float32(np.log(np.float32(1.0) - sigma) - np.log(sigma))

    @staticmethod
    def _coefficient(value: float | np.float32, dtype: mx.Dtype) -> mx.array:
        return mx.array(float(value), dtype=dtype)

    def _predict(self, sample: mx.array, order: int) -> mx.array:
        if self.step_index is None:
            raise RuntimeError("scheduler step index is not initialized")
        m0 = self.model_outputs[-1]
        if m0 is None:
            raise RuntimeError("predictor requires the current converted model output")
        index = self.step_index
        sigma_t = self.sigmas[index + 1]
        sigma_s0 = self.sigmas[index]
        alpha_t = np.float32(1.0) - sigma_t
        lambda_t = self._lambda(sigma_t) if sigma_t else np.float32(np.inf)
        lambda_s0 = self._lambda(sigma_s0)
        h = np.float32(lambda_t - lambda_s0)
        h_phi_1 = np.float32(np.expm1(np.float32(-h)))
        result = (
            self._coefficient(sigma_t / sigma_s0, sample.dtype) * sample
            - self._coefficient(alpha_t * h_phi_1, sample.dtype) * m0
        )
        if order == 2:
            previous = self.model_outputs[-2]
            if previous is None:
                raise RuntimeError("second-order predictor requires one history output")
            lambda_previous = self._lambda(self.sigmas[index - 1])
            rk = np.float32((lambda_previous - lambda_s0) / h)
            difference = (previous - m0) / self._coefficient(rk, sample.dtype)
            result = result - self._coefficient(alpha_t * h_phi_1 * 0.5, sample.dtype) * difference
        return result.astype(sample.dtype)

    def _correct(
        self,
        current_model_output: mx.array,
        last_sample: mx.array,
        current_sample: mx.array,
        order: int,
    ) -> mx.array:
        if self.step_index is None:
            raise RuntimeError("scheduler step index is not initialized")
        previous_model_output = self.model_outputs[-1]
        if previous_model_output is None:
            raise RuntimeError("corrector requires one history output")
        index = self.step_index
        sigma_t = self.sigmas[index]
        sigma_s0 = self.sigmas[index - 1]
        alpha_t = np.float32(1.0) - sigma_t
        lambda_t = self._lambda(sigma_t)
        lambda_s0 = self._lambda(sigma_s0)
        h = np.float32(lambda_t - lambda_s0)
        hh = np.float32(-h)
        h_phi_1 = np.float32(np.expm1(hh))
        result = (
            self._coefficient(sigma_t / sigma_s0, current_sample.dtype) * last_sample
            - self._coefficient(alpha_t * h_phi_1, current_sample.dtype) * previous_model_output
        )
        if order == 1:
            correction = self._coefficient(0.5, current_sample.dtype) * (
                current_model_output - previous_model_output
            )
        elif order == 2:
            older_model_output = self.model_outputs[-2]
            if older_model_output is None:
                raise RuntimeError("second-order corrector requires two history outputs")
            lambda_older = self._lambda(self.sigmas[index - 2])
            rk = np.float32((lambda_older - lambda_s0) / h)
            h_phi_k = np.float32(h_phi_1 / hh - 1.0)
            b0 = np.float32(h_phi_k / h_phi_1)
            h_phi_k = np.float32(h_phi_k / hh - 0.5)
            b1 = np.float32(2.0 * h_phi_k / h_phi_1)
            coefficients = np.linalg.solve(
                np.array([[1.0, 1.0], [rk, 1.0]], dtype=np.float32),
                np.array([b0, b1], dtype=np.float32),
            ).astype(np.float32)
            history_difference = (older_model_output - previous_model_output) / self._coefficient(
                rk, current_sample.dtype
            )
            correction = self._coefficient(
                coefficients[0], current_sample.dtype
            ) * history_difference + self._coefficient(coefficients[1], current_sample.dtype) * (
                current_model_output - previous_model_output
            )
        else:
            raise ValueError("corrector order must be one or two")
        result = result - self._coefficient(alpha_t * h_phi_1, current_sample.dtype) * correction
        return result.astype(current_sample.dtype)

    def step(self, model_output: mx.array, timestep: int, sample: mx.array) -> mx.array:
        """Advance one sequential inference step and return the previous sample."""

        if not len(self.timesteps):
            raise RuntimeError("set_timesteps must be called before step")
        if self.step_index is None:
            self._initialize_step_index(timestep)
        assert self.step_index is not None
        if self.step_index >= len(self.timesteps):
            raise RuntimeError("scheduler has already completed all inference steps")
        if int(self.timesteps[self.step_index]) != int(timestep):
            raise ValueError("scheduler steps must follow the configured timestep order")
        if model_output.shape != sample.shape:
            raise ValueError("model output and sample must have identical shapes")
        sigma = self.sigmas[self.step_index]
        converted = sample - self._coefficient(sigma, sample.dtype) * model_output
        if self.step_index > 0 and self.last_sample is not None:
            sample = self._correct(converted, self.last_sample, sample, self.this_order)
        self.model_outputs[0] = self.model_outputs[1]
        self.model_outputs[1] = converted
        self.timestep_list[0] = self.timestep_list[1]
        self.timestep_list[1] = int(timestep)
        remaining = len(self.timesteps) - self.step_index
        order = min(self.configuration.solver_order, remaining)
        self.this_order = min(order, self.lower_order_nums + 1)
        if self.this_order <= 0:
            raise RuntimeError("invalid UniPC predictor order")
        self.last_sample = sample
        previous_sample = self._predict(sample, self.this_order)
        self.lower_order_nums = min(self.lower_order_nums + 1, self.configuration.solver_order)
        self.step_index += 1
        return previous_sample

    def state_tensors(self) -> dict[str, mx.array]:
        """Return the evaluated tensor history needed for an exact continuation."""

        tensors: dict[str, mx.array] = {}
        for index, value in enumerate(self.model_outputs):
            if value is not None:
                tensors[f"model_output_{index}"] = value
        if self.last_sample is not None:
            tensors["last_sample"] = self.last_sample
        mx.eval(*tensors.values())
        return tensors

    def state_metadata(self) -> dict[str, str]:
        """Return the scalar history needed for an exact continuation."""

        return {
            "step_index": str(-1 if self.step_index is None else self.step_index),
            "lower_order_nums": str(self.lower_order_nums),
            "this_order": str(self.this_order),
            "timestep_list": ",".join(
                str(-1 if value is None else value) for value in self.timestep_list
            ),
        }

    def restore_state(
        self, tensors: dict[str, mx.array], metadata: dict[str, str]
    ) -> None:
        """Restore a state captured after a completed scheduler step."""

        try:
            step_index = int(metadata["step_index"])
            lower_order_nums = int(metadata["lower_order_nums"])
            this_order = int(metadata["this_order"])
            timestep_values = [int(value) for value in metadata["timestep_list"].split(",")]
        except (KeyError, ValueError) as error:
            raise ValueError("invalid Flow UniPC checkpoint metadata") from error
        if (
            step_index < 0
            or step_index > len(self.timesteps)
            or lower_order_nums not in range(self.configuration.solver_order + 1)
            or this_order not in range(self.configuration.solver_order + 1)
            or len(timestep_values) != self.configuration.solver_order
        ):
            raise ValueError("Flow UniPC checkpoint state is out of range")
        outputs = [tensors.get(f"model_output_{index}") for index in range(2)]
        last_sample = tensors.get("last_sample")
        if step_index > 0 and (outputs[-1] is None or last_sample is None):
            raise ValueError("Flow UniPC checkpoint is missing scheduler tensor history")
        self.model_outputs = outputs
        self.last_sample = last_sample
        self.step_index = step_index
        self.lower_order_nums = lower_order_nums
        self.this_order = this_order
        self.timestep_list = [None if value == -1 else value for value in timestep_values]
