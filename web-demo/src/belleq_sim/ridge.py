"""Standardized Ridge with an unpenalized intercept, stored as auditable JSON.

Objective: ||y-Xw-b||^2 + alpha*||w||^2. No pickle or package-internal APIs.
"""
import numpy as np

def fit(x, y, alpha):
    x, y = np.asarray(x,dtype=float), np.asarray(y,dtype=float)
    mu = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1
    z = (x-mu)/scale
    intercept = float(y.mean())
    coef = np.linalg.solve(z.T@z + alpha*np.eye(z.shape[1]), z.T@(y-intercept))
    return dict(alpha=float(alpha), center=mu.tolist(), scale=scale.tolist(),
                coefficients=coef.tolist(), intercept=intercept)

def predict(model, x):
    return np.maximum(0, ((np.asarray(x,dtype=float)-model['center'])/model['scale'])
                      @np.asarray(model['coefficients'])+model['intercept'])

def metrics(y, pred):
    y, pred = np.asarray(y), np.asarray(pred)
    e = pred-y
    den = np.sum((y-y.mean())**2)
    return dict(n=len(y), mae=float(np.mean(np.abs(e))), rmse=float(np.sqrt(np.mean(e**2))),
                r2=float(1-np.sum(e**2)/den) if den>0 else None,
                mean_bias=float(e.mean()))

def features(row):
    # Known before the request. No realized hit, visits, candidate scores or answer length.
    q = row['question']
    return [float(row['experiment_method']==m) for m in
            ['semantic_sequential','broadcast','random_sequential','single_db']] + [
                len(q.encode('utf-8')), len(q.split())]

FEATURE_NAMES = ['method_semantic','method_broadcast','method_random','method_single_db',
                 'question_utf8_bytes','question_words']
