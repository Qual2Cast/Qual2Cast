"""Peer-selection adapters. No valuation outcome enters these functions."""
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

def cosine_geometry(E):
    E=np.asarray(E,dtype=float)
    if E.ndim!=2 or not np.isfinite(E).all() or np.any(np.linalg.norm(E,axis=1)==0):
        raise ValueError('Embeddings must be finite nonzero rows')
    E=E/np.linalg.norm(E,axis=1,keepdims=True)
    S=np.clip(E@E.T,-1,1); D=S.copy(); np.fill_diagonal(D,-np.inf)
    nearest=np.argsort(-D,axis=1,kind='stable')[:,:len(E)-1]
    rank=np.full(S.shape,len(E),dtype=int)
    np.put_along_axis(rank,nearest,np.arange(len(E)-1)[None,:],axis=1)
    return E,S,nearest,rank

def select_z(S, nearest, level):
    out=[]
    for i,order in enumerate(nearest):
        row=S[i,order]; sd=row.std(ddof=0)
        out.append(order[(row-row.mean())/sd>=level].tolist() if sd>1e-12 else [])
    return out

def select_mutual(nearest,rank,k):
    return [[int(j) for j in row[:k] if rank[j,i]<k] for i,row in enumerate(nearest)]

def tree_parts(E,S,kind):
    Z=linkage(E,'ward') if kind=='ward' else linkage(squareform(np.clip(1-S,0,None),checks=False),kind)
    n=len(E); parent=np.full(2*n-1,-1,dtype=int); members=[[i] for i in range(n)]+[None]*(n-1)
    for k,(a,b) in enumerate(Z[:,:2].astype(int)):
        parent[a]=parent[b]=n+k; members[n+k]=members[a]+members[b]
    return Z,members,parent

def select_tree(nearest,members,parent,min_peers=5,exact=False):
    if min_peers>=len(nearest): raise ValueError('Not enough candidates')
    out=[]
    for i,row in enumerate(nearest):
        node=i
        while len(members[node])-1<min_peers: node=parent[node]
        peers=[int(j) for j in row if j in set(members[node])]
        out.append(peers[:min_peers] if exact else peers)
    return out

def umap_clusters(E,seed=0):
    import umap
    from sklearn.cluster import HDBSCAN
    X=umap.UMAP(n_components=10,n_neighbors=15,min_dist=0.,metric='cosine',random_state=seed,n_jobs=1).fit_transform(E)
    labels={level:HDBSCAN(min_cluster_size=5,min_samples=2,cluster_selection_method=level,copy=True,n_jobs=1).fit_predict(X) for level in ['leaf','eom']}
    return X,labels

def select_clusters(nearest,rank,labels,start='eom'):
    mutual=select_mutual(nearest,rank,20); out=[]; sources=[]
    for i,row in enumerate(nearest):
        level=next((l for l in (['leaf','eom'] if start=='leaf' else ['eom']) if labels[l][i]>=0),None)
        out.append([int(j) for j in row if labels[level][j]==labels[level][i]] if level else mutual[i])
        sources.append(level or 'mutual20_fallback')
    return out,sources

def fixed_mutual(nearest,rank,k):
    worst=np.maximum(rank,rank.T)
    return [row[np.argsort(worst[i,row],kind='stable')][:k].tolist() for i,row in enumerate(nearest)]

def fixed_cluster(nearest,rank,labels,k):
    order=fixed_mutual(nearest,rank,len(nearest)-1); out=[]
    for i,row in enumerate(nearest):
        mates=[int(j) for j in row if labels[i]>=0 and labels[j]==labels[i]]
        out.append((mates+[j for j in order[i] if j not in set(mates)])[:k])
    return out

def estimate_multiple(values,similarities,global_values,method='median'):
    values=np.asarray(values,float); similarities=np.asarray(similarities,float)
    valid=np.isfinite(values)&(values>0); v=values[valid]
    if not len(v): return np.nan
    if method=='median': return float(np.median(v))
    if method=='cosine_weighted_median':
        w=np.maximum(similarities[valid],0)
        if w.sum()<=0: return np.nan
        order=np.argsort(v,kind='stable'); j=np.searchsorted(np.cumsum(w[order]),w.sum()/2)
        return float(v[order[j]])
    if method=='log_shrink_50':
        g=np.asarray(global_values,float); g=g[np.isfinite(g)&(g>0)]
        return float(np.sqrt(np.median(v)*np.median(g))) if len(g) else np.nan
    raise ValueError(method)

def paired_bootstrap(a,b,n=2000,seed=4511):
    a=np.asarray(a,float); b=np.asarray(b,float); valid=np.isfinite(a)&np.isfinite(b)
    a=a[valid]; b=b[valid]
    if not len(a): return {'paired_n':0,'delta':np.nan,'lo':np.nan,'hi':np.nan}
    draws=np.random.default_rng(seed).integers(0,len(a),(n,len(a)))
    d=np.median(a[draws],axis=1)-np.median(b[draws],axis=1)
    return {'paired_n':len(a),'delta':float(np.median(a)-np.median(b)),'lo':float(np.quantile(d,.025)),'hi':float(np.quantile(d,.975))}
