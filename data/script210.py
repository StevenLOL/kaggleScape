
# coding: utf-8

# This is about reducing the number of feature values (binning) rather than number of features. Best candidates are continuous features with lots of different values.
# 
# Although the required modules are missing on Kaggle, I did it inelegantly by copying the files from **[here](https://github.com/navicto/Discretization-MDLPC)**. All the credit goes to Victor Ruiz (see below) who is the original author.

# In[ ]:


from __future__ import print_function
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.cross_validation import StratifiedShuffleSplit
import xgboost as xgb

def timer(start_time=None):
    if not start_time:
        start_time = datetime.now()
        return start_time
    elif start_time:
        thour, temp_sec = divmod(
            (datetime.now() - start_time).total_seconds(), 3600)
        tmin, tsec = divmod(temp_sec, 60)
        print('\n Time taken: %i hours %i minutes and %s seconds.' %
              (thour, tmin, round(tsec, 2)))


# This part is identical to the two files linked above.

# In[ ]:


######
# __author__ = 'Victor Ruiz, vmr11@pitt.edu'
######
from math import log
import random


def entropy(data_classes, base=2):
    '''
    Computes the entropy of a set of labels (class instantiations)
    :param base: logarithm base for computation
    :param data_classes: Series with labels of examples in a dataset
    :return: value of entropy
    '''
    if not isinstance(data_classes, pd.core.series.Series):
        raise AttributeError('input array should be a pandas series')
    classes = data_classes.unique()
    N = len(data_classes)
    ent = 0  # initialize entropy

    # iterate over classes
    for c in classes:
        partition = data_classes[data_classes == c]  # data with class = c
        proportion = len(partition) / N
        #update entropy
        ent -= proportion * log(proportion, base)

    return ent

def cut_point_information_gain(dataset, cut_point, feature_label, class_label):
    '''
    Return de information gain obtained by splitting a numeric attribute in two according to cut_point
    :param dataset: pandas dataframe with a column for attribute values and a column for class
    :param cut_point: threshold at which to partition the numeric attribute
    :param feature_label: column label of the numeric attribute values in data
    :param class_label: column label of the array of instance classes
    :return: information gain of partition obtained by threshold cut_point
    '''
    if not isinstance(dataset, pd.core.frame.DataFrame):
        raise AttributeError('input dataset should be a pandas data frame')

    entropy_full = entropy(dataset[class_label])  # compute entropy of full dataset (w/o split)

    #split data at cut_point
    data_left = dataset[dataset[feature_label] <= cut_point]
    data_right = dataset[dataset[feature_label] > cut_point]
    (N, N_left, N_right) = (len(dataset), len(data_left), len(data_right))

    gain = entropy_full - (N_left / N) * entropy(data_left[class_label]) -         (N_right / N) * entropy(data_right[class_label])

    return gain

######
# __author__ = 'Victor Ruiz, vmr11@pitt.edu'
######
import sys
import getopt
import re

class MDLP_Discretizer(object):
    def __init__(self, dataset, testset, class_label, out_path_data, out_test_path_data, out_path_bins, features=None):
        '''
        initializes discretizer object:
            saves raw copy of data and creates self._data with only features to discretize and class
            computes initial entropy (before any splitting)
            self._features = features to be discretized
            self._classes = unique classes in raw_data
            self._class_name = label of class in pandas dataframe
            self._data = partition of data with only features of interest and class
            self._cuts = dictionary with cut points for each feature
        :param dataset: pandas dataframe with data to discretize
        :param class_label: name of the column containing class in input dataframe
        :param features: if !None, features that the user wants to discretize specifically
        :return:
        '''

        if not isinstance(dataset, pd.core.frame.DataFrame):  # class needs a pandas dataframe
            raise AttributeError('Input dataset should be a pandas data frame')

        if not isinstance(testset, pd.core.frame.DataFrame):  # class needs a pandas dataframe
            raise AttributeError('Test dataset should be a pandas data frame')

        self._data_raw = dataset #copy or original input data
        self._test_raw = testset #copy or original test data

        self._class_name = class_label

        self._classes = self._data_raw[self._class_name].unique()

        #if user specifies which attributes to discretize
        if features:
            self._features = [f for f in features if f in self._data_raw.columns]  # check if features in dataframe
            missing = set(features) - set(self._features)  # specified columns not in dataframe
            if missing:
                print ('WARNING: user-specified features %s not in input dataframe' % str(missing))
        else:  # then we need to recognize which features are numeric
            numeric_cols = self._data_raw._data.get_numeric_data().items
            self._features = [f for f in numeric_cols if f != class_label]
        #other features that won't be discretized
        self._ignored_features = set(self._data_raw.columns) - set(self._features)
        self._ignored_features_t = set(self._test_raw.columns) - set(self._features)

        #create copy of data only including features to discretize and class
        self._data = self._data_raw.loc[:, self._features + [class_label]]
        self._test = self._test_raw.loc[:, self._features]
        #pre-compute all boundary points in dataset
        self._boundaries = self.compute_boundary_points_all_features()
        #initialize feature bins with empty arrays
        self._cuts = {f: [] for f in self._features}
        #get cuts for all features
        self.all_features_accepted_cutpoints()
        #discretize self._data
        self.apply_cutpoints(out_data_path=out_path_data, out_test_path=out_test_path_data, out_bins_path=out_path_bins)

    def MDLPC_criterion(self, data, feature, cut_point):
        '''
        Determines whether a partition is accepted according to the MDLPC criterion
        :param feature: feature of interest
        :param cut_point: proposed cut_point
        :param partition_index: index of the sample (dataframe partition) in the interval of interest
        :return: True/False, whether to accept the partition
        '''
        #get dataframe only with desired attribute and class columns, and split by cut_point
        data_partition = data.copy(deep=True)
        data_left = data_partition[data_partition[feature] <= cut_point]
        data_right = data_partition[data_partition[feature] > cut_point]

        #compute information gain obtained when splitting data at cut_point
        cut_point_gain = cut_point_information_gain(dataset=data_partition, cut_point=cut_point,
                                                    feature_label=feature, class_label=self._class_name)
        #compute delta term in MDLPC criterion
        N = len(data_partition) # number of examples in current partition
        partition_entropy = entropy(data_partition[self._class_name])
        k = len(data_partition[self._class_name].unique())
        k_left = len(data_left[self._class_name].unique())
        k_right = len(data_right[self._class_name].unique())
        entropy_left = entropy(data_left[self._class_name])  # entropy of partition
        entropy_right = entropy(data_right[self._class_name])
        delta = log(3 ** k, 2) - (k * partition_entropy) + (k_left * entropy_left) + (k_right * entropy_right)

        #to split or not to split
        gain_threshold = (log(N - 1, 2) + delta) / N

        if cut_point_gain > gain_threshold:
            return True
        else:
            return False

    def feature_boundary_points(self, data, feature):
        '''
        Given an attribute, find all potential cut_points (boundary points)
        :param feature: feature of interest
        :param partition_index: indices of rows for which feature value falls whithin interval of interest
        :return: array with potential cut_points
        '''
        #get dataframe with only rows of interest, and feature and class columns
        data_partition = data.copy(deep=True)
        data_partition.sort_values(feature, ascending=True, inplace=True)

        boundary_points = []

        #add temporary columns
        data_partition['class_offset'] = data_partition[self._class_name].shift(1)  # column where first value is now second, and so forth
        data_partition['feature_offset'] = data_partition[feature].shift(1)  # column where first value is now second, and so forth
        data_partition['feature_change'] = (data_partition[feature] != data_partition['feature_offset'])
        data_partition['mid_points'] = data_partition.loc[:, [feature, 'feature_offset']].mean(axis=1)

        potential_cuts = data_partition[data_partition['feature_change'] == True].index[1:]
        sorted_index = data_partition.index.tolist()

        for row in potential_cuts:
            old_value = data_partition.loc[sorted_index[sorted_index.index(row) - 1]][feature]
            new_value = data_partition.loc[row][feature]
            old_classes = data_partition[data_partition[feature] == old_value][self._class_name].unique()
            new_classes = data_partition[data_partition[feature] == new_value][self._class_name].unique()
            if len(set.union(set(old_classes), set(new_classes))) > 1:
                boundary_points += [data_partition.loc[row]['mid_points']]

        return set(boundary_points)

    def compute_boundary_points_all_features(self):
        '''
        Computes all possible boundary points for each attribute in self._features (features to discretize)
        :return:
        '''
        boundaries = {}
        for attr in self._features:
            data_partition = self._data.loc[:, [attr, self._class_name]]
            boundaries[attr] = self.feature_boundary_points(data=data_partition, feature=attr)
        return boundaries

    def boundaries_in_partition(self, data, feature):
        '''
        From the collection of all cut points for all features, find cut points that fall within a feature-partition's
        attribute-values' range
        :param data: data partition (pandas dataframe)
        :param feature: attribute of interest
        :return: points within feature's range
        '''
        range_min, range_max = (data[feature].min(), data[feature].max())
        return set([x for x in self._boundaries[feature] if (x > range_min) and (x < range_max)])

    def best_cut_point(self, data, feature):
        '''
        Selects the best cut point for a feature in a data partition based on information gain
        :param data: data partition (pandas dataframe)
        :param feature: target attribute
        :return: value of cut point with highest information gain (if many, picks first). None if no candidates
        '''
        candidates = self.boundaries_in_partition(data=data, feature=feature)
        # candidates = self.feature_boundary_points(data=data, feature=feature)
        if not candidates:
            return None
        gains = [(cut, cut_point_information_gain(dataset=data, cut_point=cut, feature_label=feature,
                                                  class_label=self._class_name)) for cut in candidates]
        gains = sorted(gains, key=lambda x: x[1], reverse=True)

        return gains[0][0] #return cut point

    def single_feature_accepted_cutpoints(self, feature, partition_index=pd.DataFrame().index):
        '''
        Computes the cuts for binning a feature according to the MDLP criterion
        :param feature: attribute of interest
        :param partition_index: index of examples in data partition for which cuts are required
        :return: list of cuts for binning feature in partition covered by partition_index
        '''
        if partition_index.size == 0:
            partition_index = self._data.index  # if not specified, full sample to be considered for partition

        data_partition = self._data.loc[partition_index, [feature, self._class_name]]

        #exclude missing data:
        if data_partition[feature].isnull().values.any:
            data_partition = data_partition[~data_partition[feature].isnull()]

        #stop if constant or null feature values
        if len(data_partition[feature].unique()) < 2:
            return
        #determine whether to cut and where
        cut_candidate = self.best_cut_point(data=data_partition, feature=feature)
        if cut_candidate == None:
            return
        decision = self.MDLPC_criterion(data=data_partition, feature=feature, cut_point=cut_candidate)

        #apply decision
        if not decision:
            return  # if partition wasn't accepted, there's nothing else to do
        if decision:
            # try:
            #now we have two new partitions that need to be examined
            left_partition = data_partition[data_partition[feature] <= cut_candidate]
            right_partition = data_partition[data_partition[feature] > cut_candidate]
            if left_partition.empty or right_partition.empty:
                return #extreme point selected, don't partition
            self._cuts[feature] += [cut_candidate]  # accept partition
            self.single_feature_accepted_cutpoints(feature=feature, partition_index=left_partition.index)
            self.single_feature_accepted_cutpoints(feature=feature, partition_index=right_partition.index)
            #order cutpoints in ascending order
            self._cuts[feature] = sorted(self._cuts[feature])
            return

    def all_features_accepted_cutpoints(self):
        '''
        Computes cut points for all numeric features (the ones in self._features)
        :return:
        '''
        for attr in self._features:
            self.single_feature_accepted_cutpoints(feature=attr)
        return

    def apply_cutpoints(self, out_data_path=None, out_test_path=None, out_bins_path=None):
        '''
        Discretizes data by applying bins according to self._cuts. Saves a new, discretized file, and a description of
        the bins
        :param out_data_path: path to save discretized data
        :param out_test_path: path to save discretized test data
        :param out_bins_path: path to save bins description
        :return:
        '''
        pbin_label_collection = {}
        bin_label_collection = {}
        for attr in self._features:
            if len(self._cuts[attr]) == 0:
#                self._data[attr] = 'All'
                self._data[attr] = self._data[attr].values
                self._test[attr] = self._test[attr].values
                pbin_label_collection[attr] = ['No binning']
                bin_label_collection[attr] = ['All']
            else:
                cuts = [-np.inf] + self._cuts[attr] + [np.inf]
                print(attr, cuts)
                start_bin_indices = range(0, len(cuts) - 1)
                pbin_labels = ['%s_to_%s' % (str(cuts[i]), str(cuts[i+1])) for i in start_bin_indices]
                bin_labels = ['%d' % (i+1) for i in start_bin_indices]
                pbin_label_collection[attr] = pbin_labels
                bin_label_collection[attr] = bin_labels
                self._data[attr] = pd.cut(x=self._data[attr].values, bins=cuts, right=False, labels=bin_labels,
                                          precision=6, include_lowest=True)
                self._test[attr] = pd.cut(x=self._test[attr].values, bins=cuts, right=False, labels=bin_labels,
                                          precision=6, include_lowest=True)

        #reconstitute full data, now discretized
        if self._ignored_features:
        #the line below may help in removing double class column ; looks like it works
            self._data = self._data.loc[:, self._features]
            to_return_train = pd.concat([self._data, self._data_raw[list(self._ignored_features)]], axis=1)
            to_return_train = to_return_train[self._data_raw.columns] #sort columns so they have the original order
        else:
        #the line below may help in removing double class column ; looks like it works
            self._data = self._data.loc[:, self._features]
            to_return_train = self._data

        #save data as csv
        if out_data_path:
            to_return_train.to_csv(out_data_path, index=False)

        #reconstitute test data, now discretized
        if self._ignored_features:
        #the line below may help in removing double class column ; looks like it works
        #    self._test = self._test.loc[:, self._features]
            to_return_test = pd.concat([self._test, self._test_raw[list(self._ignored_features_t)]], axis=1)
            to_return_test = to_return_test[self._test_raw.columns] #sort columns so they have the original order
        else:
        #the line below may help in removing double class column ; looks like it works
        #    self._data = self._data.loc[:, self._features]
            to_return_test = self._test

        #save data as csv
        if out_test_path:
            to_return_test.to_csv(out_test_path, index=False)

        #save bins description
        if out_bins_path:
            with open(out_bins_path, 'w') as bins_file:
                print>>bins_file, 'Description of bins in file: %s' % out_data_path
                for attr in self._features:
                    print>>bins_file, 'attr: %s\n\t%s' % (attr, ', '.join([pbin_label for pbin_label in pbin_label_collection[attr]]))


# We will convert "-1" values to np.NaN so they do not contribute to calculated cutoffs. Thanks to @David Arlund who [__reminded me__](https://www.kaggle.com/c/porto-seguro-safe-driver-prediction/discussion/43886#246381) that this needed to be done in order to get corect cuts. After features are discretized, we will reverse this operation in our final files.
# 
# Here we also define features to be discretized. I am using only three features because the notbook times out otherwise. Make sure to uncomment the line below with 4 features, and maybe add a few of your own.

# In[ ]:


df_train = pd.read_csv('../input/train.csv', dtype={'id': np.int32, 'target': np.int8})
print(' Train dataset:', df_train.shape)
train = df_train.drop(['id', 'target'], axis=1)
target = df_train['target']
df_train = df_train.replace(-1, np.nan)
df_test = pd.read_csv('../input/test.csv', dtype={'id': np.int32})
print(' Test dataset:', df_test.shape)
test = df_test.drop(['id'], axis=1)
df_test = df_test.replace(-1, np.nan)

class_label='target' 
features=['ps_reg_03', 'ps_car_12', 'ps_car_14']
#features=['ps_reg_03', 'ps_car_12', 'ps_car_13', 'ps_car_14']

start_time=timer(None)
discretizer = MDLP_Discretizer(dataset=df_train, testset=df_test, class_label=class_label, features=features, out_path_data='./train-mdlp.csv', out_test_path_data='./test-mdlp.csv', out_path_bins=None)
timer(start_time)


# After reloading the new data and converting np.NaN values back to -1, we are back to the original format without missing values.
# 
# A quick comparison of continuous variables before and after modification shows a major difference.
# 
# ***EDIT: The part below does not seem to work on Kaggle. Even though the files are saved in current directory, it appears that they go into an "output" directory dictated by system. So the files can be downloaded from the "Output" tab, but I don't know how to read them directly from the notebook. Anyway, the screen output for the rest of this notebook is shown at the end.***

# In[ ]:


mdlp_train = pd.read_csv('./train-mdlp.csv', dtype={'id': np.int32, 'target': np.int8})
mdlp_train = mdlp_train.replace(np.nan, -1)
train_mdlp = mdlp_train.drop(['id', 'target'], axis=1)
mdlp_test = pd.read_csv('./test-mdlp.csv', dtype={'id': np.int32})
mdlp_test = mdlp_test.replace(np.nan, -1)
test_mdlp = mdlp_test.drop(['id'], axis=1)

cols = ['ps_reg_03', 'ps_car_12', 'ps_car_13', 'ps_car_14']
print('\n Original features:')
for col in cols:
    print('\n', col)
    print(' Unique values: %d' % (len(np.unique(train[col]))))
    if (len(np.unique(train[col]))) <= 50:
        print('', np.unique(train[col]))
    else:
        print('', np.unique(train[col])[:50])

print('\n Discretized features:')
for col in cols:
    print('\n', col)
    print(' Unique values: %d' % (len(np.unique(mdlp_train[col]))))
    if (len(np.unique(mdlp_train[col]))) <= 50:
        print('', np.unique(mdlp_train[col]))
    else:
        print('', np.unique(mdlp_train[col])[:50])


# Let's do two quick XGBoost runs with generic parameters to compare the original data versus the discretized version.

# In[ ]:


sss = StratifiedShuffleSplit(target, test_size=0.2, random_state=1001)
for train_index, test_index in sss:
    break
train_x, train_y = train.loc[train_index], target.loc[train_index]
val_x, val_y = train.loc[test_index], target.loc[test_index]
train_mdlp_x, train_y = train_mdlp.loc[train_index], target.loc[train_index]
val_mdlp_x, val_y = train_mdlp.loc[test_index], target.loc[test_index]

xgb_params = {
              'booster': 'gbtree',
              'seed': 1001,
              'gamma': 9.0,
              'colsample_bytree': 0.8,
              'silent': True,
              'nthread': 4,
              'subsample': 0.8,
              'learning_rate': 0.1,
              'eval_metric': 'auc',
              'objective': 'binary:logistic',
              'max_delta_step': 1,
              'max_depth': 5,
              'min_child_weight': 2,
             }

print('\n XGBoost on original data:\n')
d_train = xgb.DMatrix(train_x, label=train_y)
d_valid = xgb.DMatrix(val_x, label=val_y)
watchlist = [(d_train, 'train'), (d_valid, 'val')]
clf = xgb.train(xgb_params, dtrain=d_train, num_boost_round=100000, evals=watchlist, early_stopping_rounds=100, verbose_eval=50)

print('\n XGBoost on modified data:\n')
d_train = xgb.DMatrix(train_mdlp_x, label=train_y)
d_valid = xgb.DMatrix(val_mdlp_x, label=val_y)
watchlist = [(d_train, 'train'), (d_valid, 'val')]
clf = xgb.train(xgb_params, dtrain=d_train, num_boost_round=100000, evals=watchlist, early_stopping_rounds=100, verbose_eval=50)


# Looks good to me.
# 
# **Last two cells of this notebook output the following on my computer:**
# 
#      Original features:
#     
#      ps_reg_03
#      Unique values: 5013
#      [-1.          0.06123724  0.075       0.13228757  0.13693064  0.15
#       0.15411035  0.1968502   0.21065374  0.21505813  0.22638463  0.22776084
#       0.23048861  0.23717082  0.24622145  0.25124689  0.25248762  0.25372229
#       0.25495098  0.25617377  0.25860201  0.26339134  0.26457513  0.26575365
#       0.27386128  0.27613403  0.27726341  0.27838822  0.2806243   0.28173569
#       0.28284271  0.28394542  0.28504386  0.28722813  0.29047375  0.29154759
#       0.2936835   0.29580399  0.29685855  0.29790938  0.3         0.30103986
#       0.30207615  0.30310889  0.30413813  0.30516389  0.30618622  0.30720514
#       0.30923292  0.31024184]
#     
#      ps_car_12
#      Unique values: 184
#      [-1.          0.1         0.14142136  0.14832397  0.17320508  0.28284271
#       0.3088689   0.31527766  0.31559468  0.31575307  0.31606961  0.31622777
#       0.33166248  0.34641016  0.35199432  0.3524202   0.36        0.36041643
#       0.36055513  0.36878178  0.37040518  0.37255872  0.3726929   0.37416574
#       0.38639358  0.38691084  0.38729833  0.39433488  0.39471509  0.39522146
#       0.39560081  0.39724048  0.39749214  0.39761791  0.39799497  0.39812058
#       0.39837169  0.39862263  0.39874804  0.39899875  0.39937451  0.39949969
#       0.39962482  0.39974992  0.39987498  0.4         0.40841156  0.41231056
#       0.41797129  0.41964271]
#     
#      ps_car_13
#      Unique values: 70482
#      [ 0.25061907  0.28733601  0.29041151  0.29119304  0.30872304  0.30925798
#       0.31065779  0.31324086  0.31333978  0.31373516  0.31468862  0.31606438
#       0.32017557  0.3221185   0.32250312  0.32463425  0.32524625  0.32527801
#       0.32550025  0.3256589   0.32619773  0.32638769  0.32667243  0.32727273
#       0.32736741  0.32840712  0.32850148  0.32872154  0.32922398  0.32934947
#       0.33153786  0.33172477  0.33184931  0.33188044  0.33201115  0.33256454
#       0.3330922   0.33358806  0.33380476  0.33405226  0.33408318  0.33429956
#       0.33439226  0.33448493  0.33488619  0.33513288  0.33617931  0.33676266
#       0.33685468  0.33700798]
#     
#      ps_car_14
#      Unique values: 850
#      [-1.          0.10954451  0.1183216   0.13601471  0.2         0.2078461
#       0.20976177  0.21095023  0.21307276  0.21794495  0.22135944  0.22315914
#       0.2236068   0.22427661  0.23021729  0.23323808  0.23345235  0.23452079
#       0.24899799  0.26172505  0.26457513  0.27386128  0.27748874  0.2792848
#       0.28195744  0.28284271  0.28372522  0.28548205  0.28600699  0.28635642
#       0.28722813  0.28809721  0.28827071  0.28879058  0.28982753  0.29257478
#       0.29325757  0.29410882  0.29444864  0.29495762  0.29512709  0.29529646
#       0.29614186  0.29664794  0.29732137  0.29832868  0.29916551  0.3
#       0.30033315  0.30066593]
#     
#      Discretized features:
#     
#      ps_reg_03
#      Unique values: 5
#      [-1.  1.  2.  3.  4.]
#     
#      ps_car_12
#      Unique values: 6
#      [-1.  1.  2.  3.  4.  5.]
#     
#      ps_car_13
#      Unique values: 7
#      [1 2 3 4 5 6 7]
#     
#      ps_car_14
#      Unique values: 8
#      [-1.  1.  2.  3.  4.  5.  6.  7.]
#     
#      XGBoost on original data:
#     
#     [0]     train-auc:0.5   val-auc:0.5
#     Multiple eval metrics have been passed: 'val-auc' will be used for early stopping.
#     
#     Will train until val-auc hasn't improved in 100 rounds.
#     [50]    train-auc:0.667636      val-auc:0.62964
#     [100]   train-auc:0.70354       val-auc:0.636332
#     [150]   train-auc:0.724789      val-auc:0.634334
#     Stopping. Best iteration:
#     [87]    train-auc:0.696711      val-auc:0.636762
#     
#     
#      XGBoost on modified data:
#     
#     [0]     train-auc:0.5   val-auc:0.5
#     Multiple eval metrics have been passed: 'val-auc' will be used for early stopping.
#     
#     Will train until val-auc hasn't improved in 100 rounds.
#     [50]    train-auc:0.66269       val-auc:0.632063
#     [100]   train-auc:0.697454      val-auc:0.637846
#     [150]   train-auc:0.719444      val-auc:0.636979
#     [200]   train-auc:0.740215      val-auc:0.634624
#     Stopping. Best iteration:
#     [115]   train-auc:0.705178      val-auc:0.638287
#     
