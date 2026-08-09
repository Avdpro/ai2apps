// NAX (neural accelerator) variants of the Qwen3.5/3.6 affine qmm_t kernels.
//
// Same buffer ABI as qwen35_qmm.metal, but the inner loop runs on the M5
// tensor units through MLX's qmm_t_nax_tgp_impl (quantized_nax.h). This file
// is compiled into a separate metallib (omlx_qwen35_prefill_kernels_nax) with
// -mmacosx-version-min=26.2 so the classic metallib keeps its deployment
// target; the C++ op only loads it when the runtime reports NAX support.

#if __has_include(<MetalPerformancePrimitives/MetalPerformancePrimitives.h>)

// clang-format off
#include "mlx/backend/metal/kernels/utils.h"
#include "mlx/backend/metal/kernels/steel/gemm/gemm.h"
#include "mlx/backend/metal/kernels/steel/gemm/nax.h"
#include "mlx/backend/metal/kernels/steel/gemm/loader.h"
#include "mlx/backend/metal/kernels/quantized_nax.h"
// clang-format on

template <
    typename T,
    const int group_size,
    const int bits,
    const bool aligned_N,
    const int BM,
    const int BK,
    const int BN,
    const int WM,
    const int WN>
METAL_FUNC void qmm_t_nax_dynamic_impl(
    const device uint32_t* w,
    const device T* scales,
    const device T* biases,
    const device T* x,
    device T* y,
    threadgroup T* Ws,
    const constant int& K,
    const constant int& N,
    const int M,
    uint3 tid,
    uint lid,
    uint simd_gid,
    uint simd_lid) {
  (void)lid;
  constexpr int pack_factor = get_pack_factor<bits, 8>();
  constexpr int bytes_per_pack = get_bytes_per_pack<bits>();
  constexpr int BK_padded = (BK + 16 / sizeof(T));
  using loader_w_t = QuantizedBlockLoader<
      T, BN, BK, BK_padded, 1, WM * WN * SIMD_SIZE, group_size, bits>;

  const int K_w = K * bytes_per_pack / pack_factor;
  const int K_g = K / group_size;
  const int y_row = tid.y * BM;
  const int y_col = tid.x * BN;
  auto wl = (const device uint8_t*)w;
  x += y_row * static_cast<int64_t>(K);
  wl += y_col * K_w;
  scales += y_col * K_g;
  biases += y_col * K_g;
  y += y_row * static_cast<int64_t>(N) + y_col;
  loader_w_t loader_w(wl, scales, biases, K, Ws, simd_gid, simd_lid);

  constexpr short SM = BM / WM;
  constexpr short SN = BN / WN;
  constexpr short SK = 32;
  constexpr short TM = SM / 16;
  constexpr short TN = SN / 16;
  constexpr short TK = SK / 16;
  const short tm = SM * (simd_gid / WN);
  const short tn = SN * (simd_gid % WN);
  const short sgp_sm = min(int(SM), M - (y_row + tm));
  const bool is_unaligned_sm = (sgp_sm != SM);
  const short sgp_sn = aligned_N ? SN : min(int(SN), N - (y_col + tn));
  const short tgp_bn = aligned_N ? BN : min(BN, int(N - y_col));
  const bool is_unaligned_bn = aligned_N ? false : (tgp_bn != BN);

  NAXTile<float, TM, TN> Dtile;
  Dtile.clear();
  x += tm * K;
  dispatch_bool(!is_unaligned_sm, [&](auto kAlignedM) {
    dispatch_bool(aligned_N || !is_unaligned_bn, [&](auto kAlignedN) {
      for (int k = 0; k < K; k += BK) {
        threadgroup_barrier(mem_flags::mem_threadgroup);
        if constexpr (kAlignedN.value) {
          loader_w.load_unsafe();
        } else {
          loader_w.load_safe(short2(BK, tgp_bn));
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        STEEL_PRAGMA_NO_UNROLL
        for (int kk1 = 0; kk1 < BK; kk1 += SK) {
          NAXTile<T, TM, TK> Atile;
          NAXTile<T, TN, TK> Btile;
          volatile int compiler_barrier;
          if constexpr (kAlignedM.value) {
            Atile.load(x + kk1, K);
          } else {
            Atile.load_safe(x + kk1, K, short2(SK, sgp_sm));
          }
          Btile.template load<T, BK_padded, 1>(Ws + tn * BK_padded + kk1);
          tile_matmad_nax(
              Dtile,
              Atile,
              metal::bool_constant<false>{},
              Btile,
              metal::bool_constant<true>{});
          (void)compiler_barrier;
        }
        x += BK;
        loader_w.next();
      }
      threadgroup_barrier(mem_flags::mem_threadgroup);
      if constexpr (kAlignedM.value && kAlignedN.value) {
        Dtile.store(y + tm * N + tn, N);
      } else if (kAlignedM.value && sgp_sn == SN) {
        Dtile.store(y + tm * N + tn, N);
      } else {
        Dtile.store_safe(y + tm * N + tn, N, short2(sgp_sn, sgp_sm));
      }
    });
  });
}

template <
    typename T,
    const int BM,
    const int BK,
    const int BN,
    const int WM,
    const int WN>
[[kernel]] void qwen35_q4_dual_gather_qmm_t_nax(
    const device uint32_t* resident_w [[buffer(0)]],
    const device T* resident_scales [[buffer(1)]],
    const device T* resident_biases [[buffer(2)]],
    const device uint32_t* staging_w [[buffer(3)]],
    const device T* staging_scales [[buffer(4)]],
    const device T* staging_biases [[buffer(5)]],
    const device T* x [[buffer(6)]],
    const device uint32_t* segment_ids [[buffer(7)]],
    const device uint32_t* segment_starts [[buffer(8)]],
    const device uint32_t* segment_counts [[buffer(9)]],
    device T* y [[buffer(10)]],
    const constant int& K [[buffer(11)]],
    const constant int& N [[buffer(12)]],
    uint3 tid [[threadgroup_position_in_grid]],
    uint lid [[thread_index_in_threadgroup]],
    uint simd_gid [[simdgroup_index_in_threadgroup]],
    uint simd_lid [[thread_index_in_simdgroup]]) {
  constexpr uint secondary_bit = 0x80000000u;
  const uint encoded = segment_ids[tid.z];
  const uint start = segment_starts[tid.z];
  const int M = int(segment_counts[tid.z]);
  if (int(tid.y) * BM >= M) {
    return;
  }
  const uint expert = encoded & ~secondary_bit;
  const ulong packed_k = (ulong(K) * 4u) / 32u;
  const ulong groups = ulong(K) / 64u;
  const ulong w_offset = ulong(expert) * ulong(N) * packed_k;
  const ulong q_offset = ulong(expert) * ulong(N) * groups;
  const bool secondary = (encoded & secondary_bit) != 0;
  const device uint32_t* w =
      (secondary ? staging_w : resident_w) + w_offset;
  const device T* scales =
      (secondary ? staging_scales : resident_scales) + q_offset;
  const device T* biases =
      (secondary ? staging_biases : resident_biases) + q_offset;
  x += ulong(start) * ulong(K);
  y += ulong(start) * ulong(N);

  constexpr int BK_padded = (BK + 16 / sizeof(T));
  threadgroup T Ws[BN * BK_padded];
  const uint3 local_tid(tid.x, tid.y, 0);
  qmm_t_nax_dynamic_impl<T, 64, 4, true, BM, BK, BN, WM, WN>(
      w, scales, biases, x, y, Ws, K, N, M, local_tid, lid, simd_gid,
      simd_lid);
}

#define instantiate_qwen35_q4_dual_nax(type)                                 \
  instantiate_kernel(                                                         \
      "qwen35_q4_dual_gather_qmm_t_nax_" #type                              \
      "_bm_64_bk_64_bn_64_wm_2_wn_2",                                       \
      qwen35_q4_dual_gather_qmm_t_nax, type, 64, 64, 64, 2, 2)

instantiate_qwen35_q4_dual_nax(float16_t);
instantiate_qwen35_q4_dual_nax(bfloat16_t);

#define define_qwen35_q_affine_qmm_t_nax(bits)                                \
  template <                                                                   \
      typename T,                                                              \
      const int BM,                                                            \
      const int BK,                                                            \
      const int BN,                                                            \
      const int WM,                                                            \
      const int WN>                                                            \
  [[kernel]] void qwen35_q##bits##_affine_qmm_t_nax(                          \
      const device uint32_t* w [[buffer(0)]],                                  \
      const device T* scales [[buffer(1)]],                                    \
      const device T* biases [[buffer(2)]],                                    \
      const device T* x [[buffer(3)]],                                         \
      device T* y [[buffer(4)]],                                               \
      const constant int& K [[buffer(5)]],                                     \
      const constant int& N [[buffer(6)]],                                     \
      const constant int& M [[buffer(7)]],                                     \
      uint3 tid [[threadgroup_position_in_grid]],                              \
      uint lid [[thread_index_in_threadgroup]],                                \
      uint simd_gid [[simdgroup_index_in_threadgroup]],                        \
      uint simd_lid [[thread_index_in_simdgroup]]) {                           \
    constexpr int BK_padded = (BK + 16 / sizeof(T));                           \
                                                                               \
    threadgroup T Ws[BN * BK_padded];                                          \
                                                                               \
    qmm_t_nax_tgp_impl<T, 64, bits, true, BM, BK, BN, WM, WN>(                 \
        w,                                                                     \
        scales,                                                                \
        biases,                                                                \
        x,                                                                     \
        y,                                                                     \
        Ws,                                                                    \
        K,                                                                     \
        N,                                                                     \
        M,                                                                     \
        tid,                                                                   \
        lid,                                                                   \
        simd_gid,                                                              \
        simd_lid);                                                             \
  }

#define instantiate_qwen35_q_affine_qmm_t_nax(bits, type, bm, bk, bn, wm, wn) \
  instantiate_kernel(                                                         \
      "qwen35_q" #bits "_affine_qmm_t_nax_" #type "_bm_" #bm "_bk_" #bk      \
      "_bn_" #bn "_wm_" #wm "_wn_" #wn,                                      \
      qwen35_q##bits##_affine_qmm_t_nax,                                      \
      type,                                                                   \
      bm,                                                                     \
      bk,                                                                     \
      bn,                                                                     \
      wm,                                                                     \
      wn)

// Tile variants mirror qwen_q_affine_nax_variant() in qwen35_prefill.cpp.
// Variant 0 matches the tile MLX ships for affine_qmm_t_nax (64/64/64, 2x2);
// the rest are the tuning surface for the M5 sweep. BK is capped at the
// group size (64): QuantizedBlockLoader requires group_size >= columns.
#define instantiate_qwen35_q_affine_nax_variants(bits)                        \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 64, 64, 64, 2, 2);   \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 64, 64, 64, 2, 2);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 32, 64, 64, 2, 2);   \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 32, 64, 64, 2, 2);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 128, 64, 64, 2, 2);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 128, 64, 64, 2, 2); \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 64, 64, 128, 2, 2);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 64, 64, 128, 2, 2); \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 64, 32, 64, 2, 2);   \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 64, 32, 64, 2, 2);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 64, 64, 64, 4, 1);   \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 64, 64, 64, 4, 1);  \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, float16_t, 64, 64, 64, 1, 4);   \
  instantiate_qwen35_q_affine_qmm_t_nax(bits, bfloat16_t, 64, 64, 64, 1, 4)

define_qwen35_q_affine_qmm_t_nax(4)
define_qwen35_q_affine_qmm_t_nax(5)
define_qwen35_q_affine_qmm_t_nax(6)
define_qwen35_q_affine_qmm_t_nax(8)

instantiate_qwen35_q_affine_nax_variants(4);
instantiate_qwen35_q_affine_nax_variants(5);
instantiate_qwen35_q_affine_nax_variants(6);
instantiate_qwen35_q_affine_nax_variants(8);

#endif // __has_include(<MetalPerformancePrimitives/MetalPerformancePrimitives.h>)
