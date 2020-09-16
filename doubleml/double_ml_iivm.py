import numpy as np
from sklearn.utils import check_X_y
from sklearn.base import clone
from sklearn.model_selection import KFold
from sklearn.model_selection import GridSearchCV

from .double_ml import DoubleML, DoubleMLData
from .helper import check_binary_vector
from .helper import _dml_cross_val_predict


class DoubleMLIIVM(DoubleML):
    """
    Double machine learning for interactive IV regression models

    Parameters
    ----------
    obj_dml_data :
        ToDo
    ml_learners :
        ToDo
    n_folds :
        ToDo
    n_rep_cross_fit :
        ToDo
    score :
        ToDo
    dml_procedure :
        ToDo
    draw_sample_splitting :
        ToDo
    apply_cross_fitting :
        ToDo

    Examples
    --------
    >>> import doubleml as dml
    >>> from doubleml.datasets import make_iivm_data
    >>> from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    >>> ml_learners = {'ml_m': RandomForestClassifier(max_depth=2, n_estimators=10),
    >>>                'ml_g': RandomForestRegressor(max_depth=2, n_estimators=10),
    >>>                'ml_r': RandomForestClassifier(max_depth=2, n_estimators=10)}
    >>> data = make_iivm_data()
    >>> obj_dml_data = dml.DoubleMLData(data, 'y', 'd', z_col='z')
    >>> dml_iivm_obj = dml.DoubleMLIIVM(obj_dml_data, ml_learners)
    >>> dml_iivm_obj.fit()
    >>> dml_iivm_obj.summary

    Notes
    -----
    .. include:: ../../shared/models/iivm.rst
    """
    def __init__(self,
                 obj_dml_data,
                 ml_g,
                 ml_m,
                 ml_r,
                 n_folds=5,
                 n_rep_cross_fit=1,
                 score='LATE',
                 dml_procedure='dml2',
                 draw_sample_splitting=True,
                 apply_cross_fitting=True):
        super().__init__(obj_dml_data,
                         n_folds,
                         n_rep_cross_fit,
                         score,
                         dml_procedure,
                         draw_sample_splitting,
                         apply_cross_fitting)
        self.ml_g0 = clone(ml_g)
        self.ml_g1 = clone(ml_g)
        self.ml_m = ml_m
        self.ml_r0 = clone(ml_r)
        self.ml_r1 = clone(ml_r)
        self._g0_params = None
        self._g1_params = None
        self._m_params = None
        self._r0_params = None
        self._r1_params = None

    def _check_score(self, score):
        if isinstance(score, str):
            valid_score = ['LATE']
            if score not in valid_score:
                raise ValueError('invalid score ' + score +
                                 '\n valid score ' + valid_score)
        else:
            if not callable(score):
                raise ValueError('score should be either a string or a callable.'
                                 ' %r was passed' % score)
        return score

    def _check_data(self, obj_dml_data):
        assert obj_dml_data.n_treat == 1
        check_binary_vector(obj_dml_data.d, variable_name='d')
        check_binary_vector(obj_dml_data.z, variable_name='z')
        return
    
    def _get_cond_smpls(self, smpls, z):
        smpls_z0 = [(np.intersect1d(np.where(z == 0)[0], train),
                     test) for train, test in smpls]
        smpls_z1 = [(np.intersect1d(np.where(z == 1)[0], train),
                     test) for train, test in smpls]
        return smpls_z0, smpls_z1
    
    def _ml_nuisance_and_score_elements(self, obj_dml_data, smpls, n_jobs_cv):
        X, y = check_X_y(obj_dml_data.x, obj_dml_data.y)
        X, z = check_X_y(X, obj_dml_data.z)
        X, d = check_X_y(X, obj_dml_data.d)

        # get train indices for z == 0 and z == 1
        smpls_z0, smpls_z1 = self._get_cond_smpls(smpls, z)
        
        # nuisance g
        g_hat0 = _dml_cross_val_predict(self.ml_g0, X, y, smpls=smpls_z0, n_jobs=n_jobs_cv)
        g_hat1 = _dml_cross_val_predict(self.ml_g1, X, y, smpls=smpls_z1, n_jobs=n_jobs_cv)
        
        # nuisance m
        m_hat = _dml_cross_val_predict(self.ml_m, X, z, smpls=smpls, method='predict_proba', n_jobs=n_jobs_cv)[:, 1]
        
        # nuisance r
        r_hat0 = _dml_cross_val_predict(self.ml_r0, X, d, smpls=smpls_z0, method='predict_proba', n_jobs=n_jobs_cv)[:, 1]
        r_hat1 = _dml_cross_val_predict(self.ml_r1, X, d, smpls=smpls_z1, method='predict_proba', n_jobs=n_jobs_cv)[:, 1]

        if self.apply_cross_fitting:
            y_test = y
            z_test = z
            d_test = d
        else:
            # the no cross-fitting case
            test_index = self.smpls[0][0][1]
            y_test = y[test_index]
            z_test = z[test_index]
            d_test = d[test_index]

        # compute residuals
        u_hat0 = y_test - g_hat0
        u_hat1 = y_test - g_hat1
        w_hat0 = d_test - r_hat0
        w_hat1 = d_test - r_hat1

        score = self.score
        self._check_score(score)
        if isinstance(self.score, str):
            if score == 'LATE':
                psi_b = g_hat1 - g_hat0 \
                                + np.divide(np.multiply(z_test, u_hat1), m_hat) \
                                - np.divide(np.multiply(1.0-z_test, u_hat0), 1.0 - m_hat)
                psi_a = -1*(r_hat1 - r_hat0 \
                                    + np.divide(np.multiply(z_test, w_hat1), m_hat) \
                                    - np.divide(np.multiply(1.0-z_test, w_hat0), 1.0 - m_hat))
        elif callable(self.score):
            psi_a, psi_b = self.score(y_test, z_test, d_test,
                                              g_hat0, g_hat1, m_hat, r_hat0, r_hat1, smpls)

        return psi_a, psi_b

    def _ml_nuisance_tuning(self, obj_dml_data, smpls, param_grids, scoring_methods, n_folds_tune, n_jobs_cv):
        X, y = check_X_y(obj_dml_data.x, obj_dml_data.y)
        X, z = check_X_y(X, obj_dml_data.z)
        X, d = check_X_y(X, obj_dml_data.d)

        # get train indices for z == 0 and z == 1
        smpls_z0, smpls_z1 = self._get_cond_smpls(smpls, z)

        if scoring_methods is None:
            scoring_methods = {'scoring_methods_g0': None,
                               'scoring_methods_g1': None,
                               'scoring_methods_m': None,
                               'scoring_methods_r0': None,
                               'scoring_methods_r1': None}

        g0_tune_res = [None] * len(smpls)
        g1_tune_res = [None] * len(smpls)
        m_tune_res = [None] * len(smpls)
        r0_tune_res = [None] * len(smpls)
        r1_tune_res = [None] * len(smpls)

        for idx, (train_index, test_index) in enumerate(smpls):
            # cv for ml_g0
            g0_tune_resampling = KFold(n_splits=n_folds_tune)
            g0_grid_search = GridSearchCV(self.ml_g0, param_grids['param_grid_g0'],
                                         scoring=scoring_methods['scoring_methods_g0'],
                                         cv=g0_tune_resampling)
            train_index_z0 = smpls_z0[idx][0]
            g0_tune_res[idx] = g0_grid_search.fit(X[train_index_z0, :], y[train_index_z0])

            # cv for ml_g1
            g1_tune_resampling = KFold(n_splits=n_folds_tune)
            g1_grid_search = GridSearchCV(self.ml_g1, param_grids['param_grid_g1'],
                                         scoring=scoring_methods['scoring_methods_g1'],
                                         cv=g1_tune_resampling)
            train_index_z1 = smpls_z1[idx][0]
            g1_tune_res[idx] = g1_grid_search.fit(X[train_index_z1, :], y[train_index_z1])

            # cv for ml_m
            m_tune_resampling = KFold(n_splits=n_folds_tune)
            m_grid_search = GridSearchCV(self.ml_m, param_grids['param_grid_m'],
                                         scoring=scoring_methods['scoring_methods_m'],
                                         cv=m_tune_resampling)
            m_tune_res[idx] = m_grid_search.fit(X[train_index, :], z[train_index])

            # cv for ml_r0
            r0_tune_resampling = KFold(n_splits=n_folds_tune)
            r0_grid_search = GridSearchCV(self.ml_r0, param_grids['param_grid_r0'],
                                         scoring=scoring_methods['scoring_methods_r0'],
                                         cv=r0_tune_resampling)
            train_index_z0 = smpls_z0[idx][0]
            r0_tune_res[idx] = r0_grid_search.fit(X[train_index_z0, :], d[train_index_z0])

            # cv for ml_g1
            r1_tune_resampling = KFold(n_splits=n_folds_tune)
            r1_grid_search = GridSearchCV(self.ml_r1, param_grids['param_grid_r1'],
                                         scoring=scoring_methods['scoring_methods_r1'],
                                         cv=r1_tune_resampling)
            train_index_z1 = smpls_z1[idx][0]
            r1_tune_res[idx] = r1_grid_search.fit(X[train_index_z1, :], d[train_index_z1])

        g0_best_params = [xx.best_params_ for xx in g0_tune_res]
        g1_best_params = [xx.best_params_ for xx in g1_tune_res]
        m_best_params = [xx.best_params_ for xx in m_tune_res]
        r0_best_params = [xx.best_params_ for xx in r0_tune_res]
        r1_best_params = [xx.best_params_ for xx in r1_tune_res]

        params = {'g0_params': g0_best_params,
                  'g1_params': g1_best_params,
                  'm_params': m_best_params,
                  'r0_params': r0_best_params,
                  'r1_params': r1_best_params}

        tune_res = {'g0_tune': g0_tune_res,
                    'g1_tune': g1_tune_res,
                    'm_tune': m_tune_res,
                    'r0_tune': r0_tune_res,
                    'r1_tune': r1_tune_res}

        res = {'params': params,
               'tune_res': tune_res}

        return(res)

    def _set_ml_nuisance_params(self, params):
        self._g0_params = params['g0_params']
        self._g1_params = params['g1_params']
        self._m_params = params['m_params']
        self._r0_params = params['r0_params']
        self._r1_params = params['r1_params']
