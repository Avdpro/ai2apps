#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include "expert_loader.h"
namespace nb=nanobind;
NB_MODULE(_dsv41_loader,m) {
 m.def("abi_probe",[](const mlx::core::array& a){return a.size();});
 m.def("preadv_fused_experts",&omlx::glm_kernels::preadv_fused_experts,nb::call_guard<nb::gil_scoped_release>());
}
