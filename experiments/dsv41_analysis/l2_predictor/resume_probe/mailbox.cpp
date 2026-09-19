#include <algorithm>
#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <mlx/ops.h>
#include <mlx/primitives.h>
#include <mlx/backend/metal/device.h>
#include <mlx/backend/metal/utils.h>
#include <mlx/allocator.h>
#include <mutex>
namespace mx=mlx::core;namespace nb=nanobind;
struct State {std::mutex mutex;std::vector<std::vector<int>> ready;};
struct Mailbox {
 std::shared_ptr<State> state=std::make_shared<State>();
 std::vector<std::vector<int>> drain(){std::lock_guard<std::mutex> lock(state->mutex);std::vector<std::vector<int>> out;out.swap(state->ready);return out;}
};
class Notify:public mx::Primitive {
 std::shared_ptr<State> state;int sequence;
 public:
 Notify(std::shared_ptr<State> s,int seq):mx::Primitive(mx::default_stream(mx::Device::gpu)),state(s),sequence(seq){}
 const char* name()const override{return "L2AsyncNotify";}
 void eval_cpu(const std::vector<mx::array>&,std::vector<mx::array>&)override{throw std::runtime_error("GPU only");}
 void eval_gpu(const std::vector<mx::array>& in,std::vector<mx::array>& out)override{
  auto &d=mx::metal::device(stream().device);int count=int(in[0].size());
  auto packet=NS::TransferPtr(d.mtl_device()->newBuffer(count*sizeof(int),MTL::ResourceStorageModeShared));
  if(!packet)throw std::runtime_error("mailbox allocation");
  std::fill_n(static_cast<int*>(packet->contents()),count,-2); // skipped GPU suffix stays invalid

  out[0].set_data(mx::allocator::malloc(out[0].nbytes()));
  auto lib=d.get_library("l2_notify",[]{return R"(
#include <metal_stdlib>
using namespace metal;
kernel void notify(device const int* ids [[buffer(0)]],device int* packet [[buffer(1)]],device int* out [[buffer(2)]],constant int& count [[buffer(3)]],uint t [[thread_position_in_grid]]){if(t<count){packet[t]=ids[t];out[t]=ids[t];}}
)";});
  auto &enc=mx::metal::get_command_encoder(stream());enc.set_compute_pipeline_state(d.get_kernel("notify",lib));enc.set_input_array(in[0],0);enc.set_buffer(packet.get(),1);enc.set_output_array(out[0],2);enc.set_bytes(count,3);enc.dispatch_threads(MTL::Size(count,1,1),MTL::Size(count,1,1));
  auto owner=state;int seq=sequence;
  enc.get_command_buffer()->addCompletedHandler([packet,owner,count,seq](MTL::CommandBuffer* completed){std::vector<int> row;row.reserve(count+1);row.push_back(seq);if(completed->status()==MTL::CommandBufferStatusError){row.push_back(-1);std::lock_guard<std::mutex> lock(owner->mutex);owner->ready.push_back(std::move(row));return;}auto ptr=static_cast<const int*>(packet->contents());row.insert(row.end(),ptr,ptr+count);std::lock_guard<std::mutex> lock(owner->mutex);owner->ready.push_back(std::move(row));});
 }
};
NB_MODULE(_l2_window_mailbox,m){nb::class_<Mailbox>(m,"Mailbox").def(nb::init<>()).def("drain",&Mailbox::drain);m.def("notify",[](Mailbox& box,const mx::array& ids,int sequence){if(ids.dtype()!=mx::int32||ids.ndim()!=1||ids.size()<1||ids.size()>64)throw std::runtime_error("expected 1..64 int32 IDs");return mx::array(ids.shape(),mx::int32,std::make_shared<Notify>(box.state,sequence),{ids});});}
