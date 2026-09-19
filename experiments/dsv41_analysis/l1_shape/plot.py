"""Plot the fitted allocation and its measured training costs, never synthetic results."""
import json
from pathlib import Path
import numpy as np

def render(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    candidate=json.loads((root/'candidate/frozen.json').read_text())
    cap=np.array(candidate['capacities']);cost=np.array(candidate['per_layer_training_costs']);levels=[32,36,40,44,48]
    chosen=np.array([cost[l,levels.index(int(c)),0] for l,c in enumerate(cap)])
    saved=cost[:,2,0]-chosen;layers=np.arange(40)
    fig,ax=plt.subplots(2,1,figsize=(12,6),sharex=True,layout='constrained')
    ax[0].step(layers,cap,where='mid',color='#285e9c',linewidth=1.6)
    ax[0].scatter(layers,cap,s=18,color='#285e9c')
    ax[0].axhline(40,color='#666666',linestyle='--',linewidth=1,label='Uniform Main40')
    ax[0].set(ylim=(30,50),yticks=levels,ylabel='Main slots',title='DS4.1F: 1600 Main slots total, Hot8 per layer')
    ax[0].legend(loc='upper right');ax[0].grid(axis='y',alpha=.2)
    ax[1].bar(layers,saved,color=np.where(saved>=0,'#257f65','#bd6045'))
    ax[1].axhline(0,color='#777777',linewidth=.8)
    ax[1].set(xlabel='Layer',ylabel='Expert loads saved / token',title='Training-family macro cost: uniform40 minus chosen capacity',xticks=range(0,40,2),xlim=(-1,40))
    ax[1].grid(axis='y',alpha=.2)
    out=root/'candidate/allocation.png';fig.savefig(out,dpi=150);fig.savefig(out.with_suffix('.svg'));plt.close(fig)
    return out.resolve()
if __name__=='__main__':print(render(Path('artifacts/dsv41-l1-shape-20260915')))
