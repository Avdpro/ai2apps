#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include "expert_loader.h"
#include <cstring>
#include <set>
#include <stdexcept>
namespace nb=nanobind;
namespace {
// Caller must materialize lazy consumers and synchronize before mutation.
int64_t copy_expert_slots(const std::vector<int>& sources,
                         const std::vector<int>& targets,
                         const std::vector<mlx::core::array>& arrays) {
 if(sources.size()!=targets.size() || arrays.size()!=6)
  throw std::invalid_argument("copy requires matching slots and six expert buffers");
 if(sources.empty()) return 0;
 if(arrays[0].ndim()<1 || arrays[0].shape(0)<=0)
  throw std::invalid_argument("invalid copy capacity");
 const int capacity=arrays[0].shape(0);
 std::set<int> src(sources.begin(),sources.end()), dst(targets.begin(),targets.end());
 if(dst.size()!=targets.size()) throw std::invalid_argument("duplicate copy destinations");
 for(int s:sources) if(s<0 || s>=capacity || dst.count(s))
  throw std::invalid_argument("copy source invalid or overlaps destinations");
 for(int d:targets) if(d<0 || d>=capacity)
  throw std::invalid_argument("copy destination out of range");
 struct Buffer {uint8_t* ptr;size_t stride;};
 std::vector<Buffer> buffers;
 for(const auto& a:arrays) {
  if(a.ndim()<1 || a.shape(0)!=capacity || a.dtype()!=mlx::core::uint8 ||
     !a.flags().row_contiguous || !a.is_available() || a.nbytes()%capacity)
   throw std::invalid_argument("copy needs evaluated contiguous uint8 expert buffers");
  buffers.push_back({const_cast<mlx::core::array&>(a).data<uint8_t>(),a.nbytes()/capacity});
 }
 // Every input has been checked before the first write. Hot and Main are disjoint.
 int64_t bytes=0;
 for(size_t i=0;i<sources.size();++i) for(const auto& b:buffers) {
  std::memcpy(b.ptr+targets[i]*b.stride,b.ptr+sources[i]*b.stride,b.stride);
  bytes+=b.stride;
 }
 return bytes;
}
}
NB_MODULE(_dsv41_loader,m) {
 m.def("abi_probe",[](const mlx::core::array& a){return a.size();});
 m.def("preadv_fused_experts",&omlx::glm_kernels::preadv_fused_experts,nb::call_guard<nb::gil_scoped_release>());
 m.def("copy_expert_slots",&copy_expert_slots,nb::call_guard<nb::gil_scoped_release>());
}
