"""Text representations, reciprocal fusion and team peer selectors."""
import numpy as np
import pandas as pd
from matching.peer_selectors import (cosine_geometry,select_z,select_mutual,tree_parts,select_tree,select_clusters)

class CandidateRetrieval:
    def __init__(self,descriptors,features,cluster_labels=None):
        self.data=descriptors.reset_index(drop=True)
        self.ids=self.data.IQ_COMPANY_ID.tolist()
        self.index={cid:i for i,cid in enumerate(self.ids)}
        self.geometry = {}
        for name, E in features.items():
            if len(E) != len(self.ids): raise ValueError('Representation rows do not align')
            self.geometry[name] = cosine_geometry(E)
        E,S,nearest,rank = self.geometry['mpnet']
        self.sets = {'z2':select_z(S,nearest,2), 'mutual20':select_mutual(nearest,rank,20)}
        if cluster_labels is not None:
            self.sets['cluster_eom'] = select_clusters(nearest,rank,cluster_labels)[0]
        for kind in ['complete','ward']:
            _,members,parent = tree_parts(E,S,kind)
            self.sets['tree_'+kind] = select_tree(nearest,members,parent)


    def retrieve(self, company_id, method, limit=20, candidate_ids=None):
            i = self.index[company_id]
            allowed = set(candidate_ids) if candidate_ids is not None else set(self.ids)
            allowed.discard(company_id)
            if method in ('mpnet','tfidf','lsa'):
                _,S,nearest,_ = self.geometry[method]; order = nearest[i]; scores = S[i]
                measure = method+'_cosine'
            elif method == 'rrf':
                scores = np.zeros(len(self.ids))
                for name in ['mpnet','tfidf','lsa']:
                    order = self.geometry[name][2][i]
                    scores[order] += 1/(60+np.arange(1,len(order)+1))
                order = np.argsort(-scores,kind='stable'); measure = 'reciprocal_rank_fusion_c60'
            elif method in self.sets:
                order = self.sets[method][i]; scores = self.geometry['mpnet'][1][i]
                measure = 'mpnet_cosine_with_'+method+'_membership'
            else:
                raise ValueError('Unavailable selector: '+method)
            order = [int(j) for j in order if self.ids[j] in allowed][:limit]
            return pd.DataFrame([{'peer_id':self.ids[j],'peer':self.data.target_ciq_ticker[j],
                                  'retrieval_rank':r,'retrieval_score':float(scores[j]),'measure':measure,
                                  'source_urls':self.data.urls[j]} for r,j in enumerate(order,1)],
                                columns=['peer_id','peer','retrieval_rank','retrieval_score','measure','source_urls'])
