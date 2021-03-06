#!/usr/bin/env python
# coding=utf-8

# Created by max on 17-11-23

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pandas import Series, DataFrame

import sklearn.metrics as metrics
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA, KernelPCA, SparsePCA
from sklearn.manifold import TSNE

from matplotlib.patches import Ellipse

from keras.models import Sequential
from keras.layers import Dense
from keras.layers import LSTM
from keras.layers import Activation, Dropout
from keras.models import load_model
from keras.callbacks import EarlyStopping, ModelCheckpoint

sys.path.append(os.path.dirname(__file__))

from tsbitmaps.tsbitmapper import TSBitMapper
from util import arff

DATASET_PATH = "../dataset/mts/labeled/data2_occupancy_ad_5d.csv"

dataset_trainrange = {
    "../dataset/mts/labeled/data1_occupancy_ad_5d.csv": (2900, 6654),
    "../dataset/mts/labeled/data2_occupancy_ad_5d.csv": (3081, 6830),
    "../dataset/mts/labeled/data3_occupancy_ad_5d.csv": (2900, 6654),
    "../dataset/mts/labeled/eeg_eye_state_14d.csv": (9057, 11105)
}


def precision_score(true_y, pred_y, decimals=3):
    p = metrics.precision_score(true_y, pred_y)
    if decimals:
        return round(p, ndigits=decimals)
    else:
        return p


def recall_score(true_y, pred_y, decimals=3):
    r = metrics.recall_score(true_y, pred_y)
    if decimals:
        return round(r, ndigits=decimals)
    else:
        return r


def f1_score(true_y, pred_y, decimals=3):
    f1 = metrics.f1_score(true_y, pred_y)
    if decimals:
        return round(f1, ndigits=decimals)
    else:
        return f1


def plot_mts_anomalies(mts,
                       label_obserced_index,
                       label_predicted_index,
                       dataset_name,
                       label_obserced_anomaly=1,
                       label_predicted_anomaly=1,
                       dimension_show=None):
    """Plot Anomalies of MTS

    Args:
        mts (DataFrame): MTS DataFrame or MTS Result DataFrame (with predicted labels attached).
        label_obserced_index (int): label index of observation.
        label_predicted_index (int): label index of predication. None for only plot observations.
        dataset_name (str): show in plot title.
        label_obserced_anomaly (str or int): 1 or 'a' or other. `1` for Default.
        label_predicted_anomaly (str or int): 1 or 'a' or other. None for only plot observations. `1` for Default.
        dimension_show (int): control the number of dimensions to show in plot. None for show all dimensions.

    """
    if not dimension_show:
        if label_predicted_index is not None:
            features = mts.shape[1] - 2
        else:
            features = mts.shape[1] - 1
        print("Features=", features)
    else:
        features = dimension_show

    # Observed and Predicated Anomalies
    anomalies_observed = mts.iloc[:, :label_obserced_index][mts.iloc[:, label_obserced_index] == label_obserced_anomaly]

    if label_predicted_index is not None:
        anomalies_predicted = mts.iloc[:, :label_obserced_index][
            mts.iloc[:, label_predicted_index] == label_predicted_anomaly]

    # Plot
    fig, axes = plt.subplots(features, 1, sharex='all')
    for i in range(features):
        ax = axes[i]
        ax.plot(mts.iloc[:, i], color='black')
        ax.set_ylabel("{}".format(mts.columns[i]))

        x0, y0 = ax.transAxes.transform((0, 0))  # lower left in pixels
        x1, y1 = ax.transAxes.transform((1, 1))  # upper right in pixes
        dx = x1 - x0
        dy = y1 - y0
        maxd = max(dx, dy)
        width = 2.5 * maxd / dx
        height = 2.5 * maxd / dy

        if i == 0:
            ax.set_title("Anomalies of {}".format(dataset_name[dataset_name.rfind('/') + 1:]))

        if i == features - 1:
            ax.set_xlabel("Time")

        # Plot Observed Anomalies
        for x, y in zip(anomalies_observed.index, anomalies_observed.values[:, i]):
            xy = (x, y)
            circle = Ellipse(xy, width, height, fill=False, edgecolor='green')
            ax.add_patch(circle)

        # Plot Predicted Anomalies
        if label_predicted_index is not None:
            for x, y in zip(anomalies_predicted.index, anomalies_predicted.values[:, i]):
                xy = (x + 0.2, y + 0.2)
                circle = Ellipse(xy, width, height, fill=False, edgecolor='red')
                ax.add_patch(circle)

    plt.grid()
    plt.show()


def plot_uts_anomalies(df, label_anomaly, dataset_name):
    """Plot Anomalies of UTS

    Args:
        df (DataFrame): uts dataframe
        label_anomaly (int or str): 1 or 'o' or other
        dataset_name (str):

    """
    anomalies_observed = df[df.iloc[:, 0] == label_anomaly]

    fig, ax = plt.subplots()

    ax.plot(df.iloc[:, 0], color='black')
    ax.set_ylabel("{}".format(df.columns[0]))

    x0, y0 = ax.transAxes.transform((0, 0))  # lower left in pixels
    x1, y1 = ax.transAxes.transform((1, 1))  # upper right in pixes
    dx = x1 - x0
    dy = y1 - y0
    maxd = max(dx, dy)
    width = 2.5 * maxd / dx
    height = 2.5 * maxd / dy

    ax.set_title("Outliers on {} dataset".format(dataset_name))
    ax.set_xlabel("Time")

    for x, y in zip(anomalies_observed.index, anomalies_observed.values):
        xy = (x, y)
        circle = Ellipse(xy, width, height, fill=False, edgecolor='red')
        ax.add_patch(circle)

    plt.grid()
    plt.show()


def to_standardization(df):
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler = StandardScaler()
    df.loc[:, df.columns[:-1]] = scaler.fit_transform(df.loc[:, df.columns[:-1]])


def to_uts(mts, transformer):
    """PCA Dimension Reduction. Convert MTS to UTS

    Args:
        mts (ndarray): MTS
        transformer (class): PCA, KernelPCA, TSNE

    Returns:
        ndarray: UTS

    """
    model = PCA(n_components=1)
    if transformer == KernelPCA:
        model = KernelPCA(n_components=1, kernel="rbf")
    elif transformer == TSNE:
        model = TSNE(n_components=1, perplexity=40, n_iter=300)

    uts = model.fit_transform(mts)
    uts = uts.reshape(-1)
    return uts


def main(args):
    # 0. Automatic Test
    case_count = 1
    transformers = [KernelPCA, TSNE]
    threshold_range = range(0, 101, 10)

    # 1. Load MTS Data
    # df = arff_to_mtss_df(DATASET_PATH, dtype=np.float, tag_type=np.int, tag_anomaly=1)
    df = pd.read_csv(DATASET_PATH, index_col='t')

    # 2. Standardization
    to_standardization(df)

    # 3. To UTS
    mts = df.values[:, :-1]

    for transformer in transformers:
        print("Transformer: ", transformer.__name__)

        uts = to_uts(mts, transformer)

        # For LSTM
        train = []
        train_start = dataset_trainrange[DATASET_PATH][0]
        train_end = dataset_trainrange[DATASET_PATH][1]
        timestep = 100
        for index in range(train_start, train_end - timestep + 1):
            train.append(uts[index: index + timestep])
        train = np.array(train).astype(np.float64)
        train_x = train[:, :-1]
        train_y = train[:, -1]

        test = []
        for index in range(len(uts) - timestep + 1):
            test.append(uts[index: index + timestep])
        test = np.array(test).astype(np.float64)
        test_x = test[:, :-1]
        test_y = test[:, -1]

        true_y = df.iloc[:, -1].values
        true_y = true_y[timestep - 1:]

        train_x = train_x.reshape((train_x.shape[0], 1, train_x.shape[1]))
        test_x = test_x.reshape((test_x.shape[0], 1, test_x.shape[1]))

        # Repeat 10 experiments
        result_scores_avg = []
        for case in range(case_count):
            print("Case #", case)

            # 4. Anomaly Detection
            # LSTM
            model = Sequential()
            model.add(LSTM(64, input_shape=(train_x.shape[1], train_x.shape[2]), return_sequences=True))
            model.add(Dropout(0.2))
            model.add(LSTM(units=256, return_sequences=True))
            model.add(Dropout(0.2))
            model.add(LSTM(units=100, return_sequences=False))
            model.add(Dropout(0.2))
            model.add(Dense(1))

            model.compile(loss="mse", optimizer="rmsprop")
            model.fit(train_x, train_y, batch_size=50, epochs=100, validation_split=0.05, verbose=2)

            result_scores = []
            for q in threshold_range:
                prediction = model.predict(test_x)
                prediction = prediction.reshape(-1)

                error_rmse = np.sqrt(((test_y - prediction) ** 2) / len(test_y))

                threshold = np.percentile(error_rmse, q)
                pred_y = np.full(len(error_rmse), -1)
                pred_y[error_rmse > threshold] = 1

                # 5. Caculate Scores
                precision = precision_score(true_y, pred_y)
                recall = recall_score(true_y, pred_y)
                f1 = f1_score(true_y, pred_y)

                result_scores.append([q, precision, recall, f1])

            result_scores_avg.append(DataFrame(result_scores).set_index(0))

        # 6. Save avg scores to file
        result_scores_avg = pd.concat(result_scores_avg)
        result_scores_avg = result_scores_avg.groupby(level=0).mean().round(3)
        pd.DataFrame(result_scores_avg).to_csv(
            "LSTM-{}-scores-{}.csv".format(DATASET_PATH.split('/')[-1][:-4], transformer.__name__),
            index_label='q',
            header=['p', 'r', 'f1'])

    # 6. Plot MTSS Anomalies
    # mts_result_df = pd.concat([df, Series(pred_y)], axis=1)
    # plot_mts_anomalies(mts_result_df, label_obserced_index=-2, label_predicted_index=-1,
    #                    dataset_name=DATASET_PATH)

    # plt.plot(uts)
    # plt.title("Standardized UTS - EEG Eye State")

    # plot_anomalies(df, df.shape[1] - 1, 1, DATASET_NAME, dimension_show=6)

    # df.loc[:, df.columns[:-1]].plot(subplots=False, title="Original MTS - EEG Eye State")

    plt.show()


if __name__ == "__main__":
    start = time.time()
    print("Start: " + str(start))

    main(sys.argv[1:])

    elapsed = (time.time() - start)
    print("Used {0:0.3f} seconds".format(elapsed))
