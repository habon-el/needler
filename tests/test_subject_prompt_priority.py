import numpy as np
from PIL import Image
from embroiderly import subject_model as subject


def test_keep_remove_hints_rank_before_model_confidence():
    class Model:
        def set_image(self, image): pass
        def predict(self, **kwargs):
            correct = np.zeros((40,40), bool); correct[10:30,10:30]=True
            missing = correct.copy(); missing[15,15]=False
            background = correct.copy(); background[5,5]=True
            return np.array([missing,background,correct]), np.array([.99,.98,.6]), None
    subject._cache.clear()
    try:
        mask,info=subject.propose_mask(Image.new('RGBA',(40,40),'red'),
            [{'point':[15,15],'label':1},{'point':[5,5],'label':0}], factory=Model)
        assert mask[15,15] and not mask[5,5]
        assert info['prompt_conflicts']==0
        assert info['candidates'][0]['score']==.6
        assert info['candidates'][1]['prompt_conflicts']==1
    finally: subject._cache.clear()


def test_conflicting_candidate_is_reported_not_claimed_exact():
    class Model:
        def set_image(self,image): pass
        def predict(self,**kwargs): return np.ones((1,40,40),bool), np.array([.9]),None
    subject._cache.clear()
    try:
        _,info=subject.propose_mask(Image.new('RGBA',(40,40),'red'),
            [{'point':[15,15],'label':1},{'point':[5,5],'label':0}],factory=Model)
        assert info['prompt_conflicts']==1
    finally: subject._cache.clear()
