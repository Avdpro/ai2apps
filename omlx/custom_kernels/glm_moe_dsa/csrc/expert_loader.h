#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include <mlx/mlx.h>

namespace omlx::glm_kernels {

int64_t preadv_fused_experts(
    int fd,
    int64_t data_offset,
    int64_t record_bytes,
    const std::vector<int>& expert_ids,
    const std::vector<int>& slots,
    const mlx::core::array& gate_up_weight,
    const mlx::core::array& gate_up_scales,
    const mlx::core::array& gate_up_biases,
    const mlx::core::array& down_weight,
    const mlx::core::array& down_scales,
    const mlx::core::array& down_biases,
    int io_workers = 4);

} // namespace omlx::glm_kernels
