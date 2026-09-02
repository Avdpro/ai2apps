#include "expert_loader.h"

#include <sys/stat.h>
#include <sys/uio.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <exception>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace omlx::glm_kernels {
namespace {

struct Destination {
  uint8_t* base;
  size_t slot_bytes;
};

Destination destination(const mlx::core::array& value, int capacity) {
  if (value.ndim() < 1 || value.shape(0) != capacity) {
    throw std::invalid_argument("expert destination capacity mismatch");
  }
  if (!value.flags().row_contiguous || value.nbytes() % capacity != 0) {
    throw std::invalid_argument("expert destination must be row-contiguous");
  }
  if (!value.is_available()) {
    throw std::invalid_argument(
        "expert destination must be evaluated and synchronized before preadv");
  }
  auto& mutable_value = const_cast<mlx::core::array&>(value);
  return {
      mutable_value.data<uint8_t>(),
      value.nbytes() / static_cast<size_t>(capacity),
  };
}

void preadv_exact(int fd, std::vector<iovec> vectors, int64_t offset) {
  size_t first = 0;
  while (first < vectors.size()) {
    const auto count = ::preadv(
        fd,
        vectors.data() + first,
        static_cast<int>(vectors.size() - first),
        static_cast<off_t>(offset));
    if (count < 0) {
      if (errno == EINTR) {
        continue;
      }
      throw std::runtime_error(
          std::string("expert preadv failed: ") + std::strerror(errno));
    }
    if (count == 0) {
      throw std::runtime_error("short read while loading fused expert");
    }
    offset += count;
    size_t consumed = static_cast<size_t>(count);
    while (first < vectors.size() && consumed >= vectors[first].iov_len) {
      consumed -= vectors[first].iov_len;
      ++first;
    }
    if (first < vectors.size() && consumed != 0) {
      vectors[first].iov_base =
          static_cast<uint8_t*>(vectors[first].iov_base) + consumed;
      vectors[first].iov_len -= consumed;
    }
  }
}

} // namespace

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
    int io_workers) {
  if (fd < 0 || data_offset < 0 || record_bytes <= 0) {
    throw std::invalid_argument("invalid expert store descriptor or layout");
  }
  if (expert_ids.size() != slots.size()) {
    throw std::invalid_argument("expert_ids and slots must have equal length");
  }
  if (expert_ids.empty()) {
    return 0;
  }
  if (io_workers < 1 || io_workers > 16) {
    throw std::invalid_argument("io_workers must be in [1, 16]");
  }

  const int capacity = gate_up_weight.shape(0);
  if (capacity <= 0) {
    throw std::invalid_argument("expert destination capacity must be positive");
  }
  const std::vector<Destination> destinations = {
      destination(gate_up_weight, capacity),
      destination(gate_up_scales, capacity),
      destination(gate_up_biases, capacity),
      destination(down_weight, capacity),
      destination(down_scales, capacity),
      destination(down_biases, capacity),
  };
  int64_t destination_bytes = 0;
  for (const auto& item : destinations) {
    destination_bytes += static_cast<int64_t>(item.slot_bytes);
  }
  if (destination_bytes != record_bytes) {
    throw std::invalid_argument(
        "fused expert record does not match destination slot layout");
  }

  struct stat file_stat {};
  if (::fstat(fd, &file_stat) != 0) {
    throw std::runtime_error(
        std::string("expert fstat failed: ") + std::strerror(errno));
  }
  for (size_t index = 0; index < expert_ids.size(); ++index) {
    const int expert = expert_ids[index];
    const int slot = slots[index];
    if (expert < 0 || slot < 0 || slot >= capacity) {
      throw std::out_of_range("expert id or L1 slot is out of range");
    }
    const int64_t end = data_offset +
        (static_cast<int64_t>(expert) + 1) * record_bytes;
    if (end > file_stat.st_size) {
      throw std::out_of_range("expert record exceeds store size");
    }
  }

  std::atomic<size_t> next{0};
  std::atomic<bool> failed{false};
  std::exception_ptr error;
  std::mutex error_mutex;
  const size_t worker_count = std::min(
      expert_ids.size(), static_cast<size_t>(io_workers));
  const auto run_worker = [&] {
    try {
      while (!failed.load(std::memory_order_relaxed)) {
        const size_t index = next.fetch_add(1, std::memory_order_relaxed);
        if (index >= expert_ids.size()) {
          break;
        }
        const int slot = slots[index];
        std::vector<iovec> vectors;
        vectors.reserve(destinations.size());
        for (const auto& item : destinations) {
          vectors.push_back({
              item.base + static_cast<size_t>(slot) * item.slot_bytes,
              item.slot_bytes,
          });
        }
        const int64_t offset = data_offset +
            static_cast<int64_t>(expert_ids[index]) * record_bytes;
        preadv_exact(fd, std::move(vectors), offset);
      }
    } catch (...) {
      failed.store(true, std::memory_order_relaxed);
      std::lock_guard<std::mutex> guard(error_mutex);
      if (!error) {
        error = std::current_exception();
      }
    }
  };
  if (worker_count == 1) {
    run_worker();
    if (error) {
      std::rethrow_exception(error);
    }
    return static_cast<int64_t>(expert_ids.size()) * record_bytes;
  }

  std::vector<std::thread> workers;
  workers.reserve(worker_count);
  for (size_t worker = 0; worker < worker_count; ++worker) {
    workers.emplace_back(run_worker);
  }
  for (auto& worker : workers) {
    worker.join();
  }
  if (error) {
    std::rethrow_exception(error);
  }
  return static_cast<int64_t>(expert_ids.size()) * record_bytes;
}

} // namespace omlx::glm_kernels
