import numpy as np
import pytest
import math

from sklearn.model_selection import KFold
from sklearn.base import clone

from sklearn.linear_model import ElasticNet

import doubleml as dml

from doubleml.tests.helper_pliv_partial_z_manual import pliv_partial_z_dml1, pliv_partial_z_dml2, \
    fit_nuisance_pliv_partial_z, boot_pliv_partial_z, tune_nuisance_pliv_partial_z


@pytest.fixture(scope='module',
                params=[ElasticNet()])
def learner_r(request):
    return request.param


@pytest.fixture(scope='module',
                params=['partialling out'])
def score(request):
    return request.param


@pytest.fixture(scope='module',
                params=['dml2'])
def dml_procedure(request):
    return request.param


@pytest.fixture(scope='module',
                params=[True, False])
def tune_on_folds(request):
    return request.param


def get_par_grid(learner):
    if learner.__class__ == ElasticNet:
        par_grid = {'l1_ratio': [.1, .5, .7, .9, .95, .99, 1], 'alpha': np.linspace(0.05, 1., 7)}
    return par_grid


@pytest.fixture(scope='module')
def dml_pliv_partial_z_fixture(generate_data_pliv_partialZ, learner_r, score, dml_procedure, tune_on_folds):
    par_grid = {'ml_r': get_par_grid(learner_r)}
    n_folds_tune = 4

    boot_methods = ['Bayes', 'normal', 'wild']
    n_folds = 2
    n_rep_boot = 503

    # collect data
    data = generate_data_pliv_partialZ
    x_cols = data.columns[data.columns.str.startswith('X')].tolist()
    z_cols = data.columns[data.columns.str.startswith('Z')].tolist()

    # Set machine learning methods for r
    ml_r = clone(learner_r)

    np.random.seed(3141)
    obj_dml_data = dml.DoubleMLData(data, 'y', ['d'], x_cols, z_cols)
    dml_pliv_obj = dml.DoubleMLPLIV._partialZ(obj_dml_data,
                                              ml_r,
                                              n_folds,
                                              dml_procedure=dml_procedure)

    # tune hyperparameters
    _ = dml_pliv_obj.tune(par_grid, tune_on_folds=tune_on_folds, n_folds_tune=n_folds_tune)

    dml_pliv_obj.fit()

    np.random.seed(3141)
    y = data['y'].values
    x = data.loc[:, x_cols].values
    d = data['d'].values
    z = data.loc[:, z_cols].values
    resampling = KFold(n_splits=n_folds,
                       shuffle=True)
    smpls = [(train, test) for train, test in resampling.split(x)]

    if tune_on_folds:
        r_params = tune_nuisance_pliv_partial_z(y, x, d, z,
                                                clone(learner_r),
                                                smpls, n_folds_tune,
                                                par_grid['ml_r'])

        r_hat = fit_nuisance_pliv_partial_z(y, x, d, z,
                                            clone(learner_r),
                                            smpls,
                                            r_params)
    else:
        xx = [(np.arange(len(y)), np.array([]))]
        r_params = tune_nuisance_pliv_partial_z(y, x, d, z,
                                                clone(learner_r),
                                                xx, n_folds_tune,
                                                par_grid['ml_r'])

        r_hat = fit_nuisance_pliv_partial_z(y, x, d, z,
                                            clone(learner_r),
                                            smpls,
                                            r_params * n_folds)

    if dml_procedure == 'dml1':
        res_manual, se_manual = pliv_partial_z_dml1(y, x, d,
                                                    z,
                                                    r_hat,
                                                    smpls, score)
    elif dml_procedure == 'dml2':
        res_manual, se_manual = pliv_partial_z_dml2(y, x, d,
                                                    z,
                                                    r_hat,
                                                    smpls, score)

    res_dict = {'coef': dml_pliv_obj.coef,
                'coef_manual': res_manual,
                'se': dml_pliv_obj.se,
                'se_manual': se_manual,
                'boot_methods': boot_methods}

    for bootstrap in boot_methods:
        np.random.seed(3141)
        boot_theta, boot_t_stat = boot_pliv_partial_z(res_manual,
                                                      y, d,
                                                      z,
                                                      r_hat,
                                                      smpls, score,
                                                      se_manual,
                                                      bootstrap, n_rep_boot,
                                                      dml_procedure)

        np.random.seed(3141)
        dml_pliv_obj.bootstrap(method=bootstrap, n_rep_boot=n_rep_boot)
        res_dict['boot_coef' + bootstrap] = dml_pliv_obj.boot_coef
        res_dict['boot_t_stat' + bootstrap] = dml_pliv_obj.boot_t_stat
        res_dict['boot_coef' + bootstrap + '_manual'] = boot_theta
        res_dict['boot_t_stat' + bootstrap + '_manual'] = boot_t_stat

    return res_dict


def test_dml_pliv_coef(dml_pliv_partial_z_fixture):
    assert math.isclose(dml_pliv_partial_z_fixture['coef'],
                        dml_pliv_partial_z_fixture['coef_manual'],
                        rel_tol=1e-9, abs_tol=1e-4)


def test_dml_pliv_se(dml_pliv_partial_z_fixture):
    assert math.isclose(dml_pliv_partial_z_fixture['se'],
                        dml_pliv_partial_z_fixture['se_manual'],
                        rel_tol=1e-9, abs_tol=1e-4)


def test_dml_pliv_boot(dml_pliv_partial_z_fixture):
    for bootstrap in dml_pliv_partial_z_fixture['boot_methods']:
        assert np.allclose(dml_pliv_partial_z_fixture['boot_coef' + bootstrap],
                           dml_pliv_partial_z_fixture['boot_coef' + bootstrap + '_manual'],
                           rtol=1e-9, atol=1e-4)
        assert np.allclose(dml_pliv_partial_z_fixture['boot_t_stat' + bootstrap],
                           dml_pliv_partial_z_fixture['boot_t_stat' + bootstrap + '_manual'],
                           rtol=1e-9, atol=1e-4)
