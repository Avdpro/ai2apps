// Independent Metal prerequisite probe. This is not a model benchmark.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdio>
#include <stdexcept>

int main() { @autoreleasepool {
  auto device = MTLCreateSystemDefaultDevice();
  NSError *error = nil;
  NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void stop(device uint* range [[buffer(0)]], uint i [[thread_position_in_grid]]) {range[1]=0;}\n"
    "kernel void work(device uint* out [[buffer(0)]], constant uint& value [[buffer(1)]], uint i [[thread_position_in_grid]]) {out[i]+=value;}\n";
  auto library = [device newLibraryWithSource:source options:nil error:&error];
  if (!library) { NSLog(@"%@", error); return 1; }
  auto descriptor = [MTLComputePipelineDescriptor new];
  descriptor.computeFunction = [library newFunctionWithName:@"work"];
  descriptor.supportIndirectCommandBuffers = YES;
  auto work = [device newComputePipelineStateWithDescriptor:descriptor options:MTLPipelineOptionNone reflection:nil error:&error];
  auto stop = [device newComputePipelineStateWithFunction:[library newFunctionWithName:@"stop"] error:&error];
  if (!work || !stop) { NSLog(@"%@",error); return 1; }
  auto icbd = [MTLIndirectCommandBufferDescriptor new];
  icbd.commandTypes=MTLIndirectCommandTypeConcurrentDispatchThreads;
  icbd.inheritPipelineState=YES; icbd.inheritBuffers=YES;
  auto icb=[device newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:1 options:MTLResourceStorageModeShared];
  auto command=[icb indirectComputeCommandAtIndex:0];
  [command concurrentDispatchThreads:MTLSizeMake(13,1,1) threadsPerThreadgroup:MTLSizeMake(8,1,1)];
  auto out=[device newBufferWithLength:64 options:MTLResourceStorageModeShared];
  auto range=[device newBufferWithLength:8 options:MTLResourceStorageModeShared];
  auto queue=[device newCommandQueue];
  for(int mode=0;mode<2;mode++) {
    memset(out.contents,0,64); ((uint32_t*)range.contents)[0]=0; ((uint32_t*)range.contents)[1]=1;
    auto cb=[queue commandBuffer]; auto enc=[cb computeCommandEncoder];
    [enc useResource:icb usage:MTLResourceUsageRead];
    [enc setComputePipelineState:work]; [enc setBuffer:out offset:0 atIndex:0];
    uint32_t value=7; [enc setBytes:&value length:4 atIndex:1];
    [enc executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:0];
    [enc memoryBarrierWithScope:MTLBarrierScopeBuffers];
    if(mode) {
      [enc setComputePipelineState:stop]; [enc setBuffer:range offset:0 atIndex:0];
      [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
      [enc memoryBarrierWithScope:MTLBarrierScopeBuffers];
    }
    [enc setComputePipelineState:work]; [enc setBuffer:out offset:0 atIndex:0];
    value=11; [enc setBytes:&value length:4 atIndex:1];
    [enc executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:0];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    if(cb.error) { NSLog(@"%@",cb.error); return 2; }
    for(int i=0;i<16;i++) {
      auto want = i<13 ? (mode?7:18) : 0;
      if(((uint32_t*)out.contents)[i]!=want) { fprintf(stderr,"mode=%d i=%d got=%u want=%d\n",mode,i,((uint32_t*)out.contents)[i],want); return 3; }
    }
    printf("%s: exact, nonuniform grid and inherited inline bytes verified\n",mode?"GPU stop":"all hit");
  }
  return 0;
}}
