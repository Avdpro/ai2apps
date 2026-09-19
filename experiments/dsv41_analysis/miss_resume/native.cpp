#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <mlx/ops.h>
#include <mlx/primitives.h>
#include <mlx/backend/metal/device.h>
#include <mlx/backend/metal/utils.h>
#include <mlx/allocator.h>
namespace mx=mlx::core;
namespace nb=nanobind;
struct Session {
  NS::SharedPtr<MTL::Buffer> state;
  mx::Stream stream;
  bool active=false;
  bool guarded=false;
  Session():stream(mx::default_stream(mx::Device::gpu)) {
    if (std::string(mx::metal::miss_resume_backend_version())!="icb-gate-barrier-v2-mlx0320")throw std::runtime_error("wrong backend ABI");
    state=NS::TransferPtr(mx::metal::device(stream.device).mtl_device()->newBuffer(4096,MTL::ResourceStorageModeShared));
    if(!state) throw std::runtime_error("status allocation failed");
  }
  void begin_impl(bool guard) {
    if(active)throw std::runtime_error("nested guard");
    memset(state->contents(),0,4096);
    auto p=(int*)state->contents();p[1]=1;p[2]=-1;
    guarded=guard;
    if(guarded)mx::metal::get_command_encoder(stream).set_miss_resume_range(state.get());
    active=true;
  }
  void begin() { begin_impl(true); }
  void begin_packet() { begin_impl(false); }
  void begin_prefix() { begin_impl(false); guarded=true; }
  std::vector<float> metadata(int capacity) {
    if(active || capacity<0 || capacity>128)throw std::runtime_error("invalid metadata read");
    auto p=(float*)state->contents()+16;return {p,p+capacity+396};
  }
  std::vector<int> finish() {
    if(!active)throw std::runtime_error("guard inactive");
    // Caller must mx.eval ALL submitted state/output roots before this call.
    if(guarded)mx::metal::get_command_encoder(stream).set_miss_resume_range(nullptr);
    active=false;
    auto p=(int*)state->contents();return {p,p+16};
  }
};
class Gate: public mx::Primitive {
 std::shared_ptr<Session> session_;int layer_;
 public:
 Gate(std::shared_ptr<Session> s,int l):mx::Primitive(s->stream),session_(s),layer_(l){}
 const char* name()const override{return "MissResumeGate";}
 void eval_cpu(const std::vector<mx::array>&,std::vector<mx::array>&)override{throw std::runtime_error("GPU only");}
 void eval_gpu(const std::vector<mx::array>& in,std::vector<mx::array>& out)override {
  if(!session_->active)throw std::runtime_error("gate outside session");
  out[0].set_data(mx::allocator::malloc(out[0].nbytes()));
  out[1].set_data(mx::allocator::malloc(out[1].nbytes()));
  auto &d=mx::metal::device(stream().device);
  auto lib=d.get_library("miss_resume_gate",[]{return R"(
#include <metal_stdlib>
using namespace metal;
kernel void gate(device const int* ids [[buffer(0)]],device const int* lookup [[buffer(1)]],device int* slots [[buffer(2)]],device int* state [[buffer(3)]],constant int& layer [[buffer(4)]],device const int* ages [[buffer(5)]],device const float* rank [[buffer(6)]],constant int& capacity [[buffer(7)]],device const uchar* x [[buffer(8)]],device uchar* held [[buffer(9)]],constant int& nbytes [[buffer(10)]],device const int* required [[buffer(11)]],uint t [[thread_position_in_grid]]) {
  for(int i=int(t);i<nbytes;i+=128)held[i]=x[i];
  if(t!=0)return;
  int count=0;
  for(int i=0;i<6;i++) {int e=ids[i];int s=lookup[e];slots[i]=s;if(s<0 && required[i])count++;}
  if(count && state[2]<0) {int j=0;for(int i=0;i<6;i++)if(slots[i]<0 && required[i])state[10+j++]=ids[i];state[2]=layer;state[3]=count;for(int i=0;i<6;i++)state[4+i]=ids[i];device float* meta=(device float*)(state+16);for(int i=0;i<capacity;i++)meta[i]=float(ages[i]);for(int i=0;i<384;i++)meta[capacity+i]=rank[i];for(int i=0;i<6;i++){meta[capacity+384+i]=float(required[i]);meta[capacity+390+i]=float(slots[i]);}state[1]=0;}
}
)";});
  auto& enc=mx::metal::get_command_encoder(stream());
  // Register every continuation dependency for cross-command-buffer fences.
  for (const auto& a : in) enc.set_input_array(a,30);
  enc.set_compute_pipeline_state(d.get_kernel("gate",lib));
  enc.set_input_array(in[1],0);enc.set_input_array(in[2],1);
  enc.set_output_array(out[1],2);enc.set_buffer(session_->state.get(),3);enc.set_bytes(layer_,4);
  enc.set_input_array(in[3],5);enc.set_input_array(in[4],6);enc.set_bytes(int(in[3].size()),7);
  enc.set_input_array(in[5],11);
  enc.set_input_array(in[0],8);enc.set_output_array(out[0],9);enc.set_bytes(int(in[0].nbytes()),10);
  enc.dispatch_threads(MTL::Size(128,1,1),MTL::Size(128,1,1));
  enc.barrier(); // Publish GPU-written execution range before any later ICB.
  if(session_->guarded)enc.set_miss_resume_range(session_->state.get());
 }
};

// Unconditional native dispatch. The host waits for this one boundary before
// constructing the current MoE, so neither predicates nor state snapshots are needed.
class Probe: public mx::Primitive {
 std::shared_ptr<Session> session_;int layer_;
 public:
 Probe(std::shared_ptr<Session> s,int l):mx::Primitive(s->stream),session_(s),layer_(l){}
 const char* name()const override{return "MissResumePacket";}
 void eval_cpu(const std::vector<mx::array>&,std::vector<mx::array>&)override{throw std::runtime_error("GPU only");}
 void eval_gpu(const std::vector<mx::array>& in,std::vector<mx::array>& out)override {
  if(!session_->active||session_->guarded)throw std::runtime_error("packet requires unguarded session");
  out[0].set_data(mx::allocator::malloc(out[0].nbytes()));
  auto &d=mx::metal::device(stream().device);
  auto lib=d.get_library("miss_resume_packet",[]{return R"(
#include <metal_stdlib>
using namespace metal;
kernel void packet(device const int* ids [[buffer(0)]],device const int* lookup [[buffer(1)]],device int* slots [[buffer(2)]],device int* state [[buffer(3)]],constant int& layer [[buffer(4)]],device const int* ages [[buffer(5)]],device const float* rank [[buffer(6)]],constant int& capacity [[buffer(7)]],device const int* required [[buffer(8)]],uint t [[thread_position_in_grid]]) {
  int count=0;
  for(int i=0;i<6;i++)if(required[i] && lookup[ids[i]]<0)count++;
  if(t<6)slots[t]=lookup[ids[t]];
  if(!count)return;
  device float* meta=(device float*)(state+16);
  for(int i=int(t);i<capacity;i+=128)meta[i]=float(ages[i]);
  for(int i=int(t);i<384;i+=128)meta[capacity+i]=rank[i];
  if(t<6){state[4+t]=ids[t];meta[capacity+384+t]=float(required[t]);meta[capacity+390+t]=float(lookup[ids[t]]);}
  if(t==0){state[2]=layer;state[3]=count;int j=0;for(int i=0;i<6;i++)if(required[i] && lookup[ids[i]]<0)state[10+j++]=ids[i];}
}
)";});
  auto& enc=mx::metal::get_command_encoder(stream());
  enc.set_compute_pipeline_state(d.get_kernel("packet",lib));
  enc.set_input_array(in[0],0);enc.set_input_array(in[1],1);
  enc.set_output_array(out[0],2);enc.set_buffer(session_->state.get(),3);enc.set_bytes(layer_,4);
  enc.set_input_array(in[2],5);enc.set_input_array(in[3],6);enc.set_bytes(int(in[2].size()),7);
  enc.set_input_array(in[4],8);
  enc.dispatch_threads(MTL::Size(128,1,1),MTL::Size(128,1,1));
 }
};

NB_MODULE(_miss_resume,m) {
 m.def("retain",[](const mx::array& a){return a;});
 nb::class_<Session>(m,"Session").def(nb::init<>()).def("begin",&Session::begin).def("begin_packet",&Session::begin_packet).def("begin_prefix",&Session::begin_prefix).def("finish",&Session::finish).def("metadata",&Session::metadata);
 m.def("probe",[](Session& s,const mx::array& ids,const mx::array& lookup,int l,const mx::array& ages,const mx::array& rank,const mx::array& required){
   if(ids.size()!=6||ids.dtype()!=mx::int32||lookup.size()!=384||lookup.dtype()!=mx::int32||ages.size()>128||ages.dtype()!=mx::int32||rank.size()!=384||rank.dtype()!=mx::float32||required.size()!=6||required.dtype()!=mx::int32)throw std::runtime_error("invalid packet layout");
   return mx::array(ids.shape(),mx::int32,std::make_shared<Probe>(std::shared_ptr<Session>(&s,[](Session*){}),l),{ids,lookup,ages,rank,required});
 });
 m.def("gate",[](Session& s,const mx::array& x,const mx::array& ids,const mx::array& lookup,int l,const mx::array& ages,const mx::array& rank,const mx::array& required,const std::vector<mx::array>& deps){
   if(ids.size()!=6||ids.dtype()!=mx::int32||lookup.size()!=384||lookup.dtype()!=mx::int32||ages.size()>128||ages.dtype()!=mx::int32||rank.size()!=384||rank.dtype()!=mx::float32||required.size()!=6||required.dtype()!=mx::int32)throw std::runtime_error("expected six int32 routes");
   // Primitive must not outlive its Python session; Python runner owns it.
   std::vector<mx::array> inputs{x,ids,lookup,ages,rank,required};inputs.insert(inputs.end(),deps.begin(),deps.end());
   return mx::array::make_arrays({x.shape(),ids.shape()},{x.dtype(),mx::int32},std::make_shared<Gate>(std::shared_ptr<Session>(&s,[](Session*){}),l),inputs);
 });
}
