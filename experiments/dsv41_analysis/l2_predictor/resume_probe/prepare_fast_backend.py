"""Isolated CPU encoding optimizations; preserve Metal kernels and predicates."""
from pathlib import Path
import shutil
base=Path('artifacts/dsv41-miss-resume-mlx-src')
dst=Path('artifacts/dsv41-resume-fast-mlx-src')
shutil.copytree(base,dst,ignore=shutil.ignore_patterns('.git'))
p=dst/'mlx/backend/metal/device.h';s=p.read_text().replace('#include <functional>','#include <functional>\n#include <array>')
s=s.replace('  std::unordered_map<std::string, NS::SharedPtr<MTL::IndirectCommandBuffer>> guarded_cache_;','''  struct GuardedHash {
    size_t operator()(const std::array<uint64_t,8>& a) const {
      size_t h=0;for(auto v:a)h^=std::hash<uint64_t>{}(v)+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);return h;
    }
  };
  std::unordered_map<std::array<uint64_t,8>, NS::SharedPtr<MTL::IndirectCommandBuffer>,GuardedHash> guarded_cache_;
  std::unordered_set<const MTL::Resource*> guarded_resources_;
  void use_guarded_resource(const MTL::Resource* resource, MTL::ResourceUsage usage);''');p.write_text(s)
p=dst/'mlx/backend/metal/device.cpp';s=p.read_text();s=s.replace('get_command_encoder()->useResource(buf, MTL::ResourceUsageRead | MTL::ResourceUsageWrite)','use_guarded_resource(buf, MTL::ResourceUsageRead | MTL::ResourceUsageWrite)').replace('get_command_encoder()->useResource(a_buf, MTL::ResourceUsageRead | MTL::ResourceUsageWrite)','use_guarded_resource(a_buf, MTL::ResourceUsageRead | MTL::ResourceUsageWrite)')
a=s.index('  std::string key=',s.index('void CommandEncoder::guarded_dispatch'));b=s.index('  auto found=',a)
s=s[:a]+'''  std::array<uint64_t,8> key={reinterpret_cast<uintptr_t>(current_pipeline_),uint64_t(threads),grid.width,grid.height,grid.depth,group.width,group.height,group.depth};
'''+s[b:]
s=s.replace('  enc->useResource(found->second.get(), MTL::ResourceUsageRead);','  use_guarded_resource(found->second.get(), MTL::ResourceUsageRead);').replace('  enc->useResource(miss_resume_range_, MTL::ResourceUsageRead | MTL::ResourceUsageWrite);','  use_guarded_resource(miss_resume_range_, MTL::ResourceUsageRead | MTL::ResourceUsageWrite);')
s=s.replace('void CommandEncoder::guarded_dispatch(', '''void CommandEncoder::use_guarded_resource(const MTL::Resource* resource, MTL::ResourceUsage usage) {
  auto enc=get_command_encoder();
  if(guarded_resources_.insert(resource).second)enc->useResource(resource,usage);
}

void CommandEncoder::guarded_dispatch(''',1)
s=s.replace('  encoder_.reset();\n  needs_barrier_', '  encoder_.reset();\n  guarded_resources_.clear();\n  needs_barrier_')
s=s.replace('icb-gate-barrier-v2-mlx0320','icb-gate-barrier-v3-mlx0320')
p.write_text(s)
print(dst)
