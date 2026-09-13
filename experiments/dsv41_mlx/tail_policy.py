"""GPU-only resident tail substitution. Selection uses biased scores; weights do not."""
import mlx.core as mx


def replace_tail(score,bias,ids,weights,required,mapping,policy,scale=1.5):
    """Required original experts must already be resident; capacity >= six."""
    resident=mapping>=0
    original=mx.any(mx.arange(score.size)[:,None]==ids[None,:],axis=1)
    keep=resident&original
    priority=mx.where(resident,mx.where(keep,mx.inf,score+bias),-mx.inf)
    chosen=mx.sort(mx.argsort(priority)[-ids.size:]).astype(mx.int32)
    same=chosen[:,None]==ids[None,:]
    must=mx.any(same&required[None,:],axis=1)
    old_weight=mx.sum(mx.where(same,weights[None,:],0),axis=1)
    raw=score[chosen]
    if policy=='fixed-top':
        tail_mass=mx.sum(mx.where(required,0,weights))
        tail_score=mx.where(must,0,raw)
        result=mx.where(must,old_weight,tail_score/(mx.sum(tail_score)+1e-20)*tail_mass)
    elif policy=='renorm':result=raw/(mx.sum(raw)+1e-20)*scale
    else:raise ValueError(policy)
    replacements=mx.sum(~mx.any(same,axis=1)).astype(mx.uint32)
    # No substitution means no need to change original rounding or weights.
    result=mx.where(replacements==0,old_weight,result)
    return chosen,result,mapping[chosen],replacements


def renormalize_retained(weights,valid,scale=1.5):
    """No substitutions: restore retained weight mass; preserve all-hit rounding."""
    retained=mx.where(valid,weights,0)
    normalized=retained/(mx.sum(retained)+1e-20)*scale
    return mx.where(mx.all(valid),weights,normalized)
