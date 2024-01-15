import os
import json
import time

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
from flask import Flask, jsonify, request


#df_users = pd.read_csv(os.environ['PATH_DF_USERS'])
df_sales = pd.read_csv(os.environ['PATH_DF_SALES'])

# эксперимент проводился с 49 до 55 день включительно
periods = {'pre_pilot': np.arange(0, 49), 'pilot': np.arange(49, 56)}

# calculating the user metric for the experiment week for every user
"""
df_sales_experiment = df_sales[
    df_sales['day'].isin(periods['pilot'])
]

df_sales_pre_experiment = df_sales[
    df_sales['day'].isin(periods['pre_pilot'])
]
"""

app = Flask(__name__)


# preparing the data
@app.route('/ping')
def ping():
    ## calculating the user metrics: total weekly spending
    global calculated_matrics
    calculated_matrics = calculate_user_metrics(data_experiment=df_sales[df_sales['day'].isin(periods['pilot'])],
                                                       data_pre_experiment=df_sales[df_sales['day'].isin(periods['pre_pilot'])],
                                                       user_id_name='user_id',
                                                       metric_name='sales'
                                                       )

    return jsonify(status='ok')

# defining the function to calculate the metric (avg of purchases by user id)
def _calculate_user_metrics_cuped(data_experiment: pd.DataFrame,
                                  data_pre_experiment: pd.DataFrame,
                                  user_id_name: str,
                                  metric_name: str
                                  ) -> pd.DataFrame:
    # calculating the metrics for the experimental period
    data_metrics_experiment = calculate_user_metrics(data_experiment, user_id_name, metric_name)

    # calculating the pre-experimental metrics
    data_metrics_pre_experiment = calculate_user_metrics(data_pre_experiment, user_id_name, metric_name)
    data_metrics_pre_experiment[f'{metric_name}_prepilot'] = data_metrics_pre_experiment[metric_name] / 7
    data_metrics_pre_experiment = data_metrics_pre_experiment.drop(metric_name, axis=1)

    # combine into one dataset
    df_combined = pd.merge(data_metrics_experiment, data_metrics_pre_experiment, on=user_id_name, how='outer')

    # fill missing values with medians
    df_combined.fillna(df_combined.median(), inplace=True)

    # calculate theta
    COVARIANCE_pre_post = np.cov(df_combined[metric_name], df_combined[f'{metric_name}_prepilot'])[0][1]
    VARIANCE_pre = np.var(df_combined[f'{metric_name}_prepilot'])
    THETA = COVARIANCE_pre_post / VARIANCE_pre

    # calculate cuped metric
    df_combined[f'{metric_name}_cuped'] = df_combined[metric_name] - THETA * df_combined[f'{metric_name}_prepilot']

    return df_combined

def calculate_user_metrics(data: pd.DataFrame,
                           user_id_name: str,
                           metric_name: str
                           ) -> pd.DataFrame:
    return data.groupby(user_id_name)[metric_name].mean().reset_index()


@app.route('/check_test', methods=['POST'])
def check_test():
    test = json.loads(request.json)['test']
    has_effect = _check_test(test)
    return jsonify(has_effect=int(has_effect))


def _check_test(test):
    group_a_one = test['group_a_one']
    group_a_two = test['group_a_two']
    group_b = test['group_b']

    # performing an AA test first
    user_a_1 = group_a_one
    user_a_2 = group_a_two
    user_b = group_b

    sales_a_1 = calculated_matrics[
        calculated_matrics['user_id'].isin(user_a_1)
    ][
        'sales'
    ].values

    sales_a_2 = calculated_matrics[
        calculated_matrics['user_id'].isin(user_a_1)
    ][
        'sales'
    ].values

    aa_test = ttest_ind(sales_a_1, sales_a_2)[1] < 0.05
    if aa_test == True:
        return False

    else:
        # running AB test
        sales_a = np.concatenate([sales_a_1, sales_a_2])

        sales_b = calculated_matrics[
            calculated_matrics['user_id'].isin(user_b)
        ][
            'sales'
        ].values

        ab_test = ttest_ind(sales_a, sales_b)[1] < 0.05

        return ab_test
