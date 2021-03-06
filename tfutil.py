"""
Inspired by https://github.com/tkarras/progressive_growing_of_gans/blob/master/tfutil.py
"""

import tensorflow as tf
import numpy as np


seed = 1337
np.random.seed(seed)
tf.set_random_seed(seed)


# ---------------------------------------------------------------------------------------------
# For convenience :)

def run(*args, **kwargs):
    return tf.get_default_session().run(*args, **kwargs)


def is_tf_expression(x):
    return isinstance(x, tf.Tensor) or isinstance(x, tf.Variable) or isinstance(x, tf.Operation)


def safe_log(x, eps=1e-12):
    with tf.name_scope("safe_log"):
        return tf.log(x + eps)


def safe_log2(x, eps=1e-12):
    with tf.name_scope("safe_log2"):
        return tf.log(x + eps) * np.float32(1. / np.log(2.))


def lerp(a, b, t):
    with tf.name_scope("lerp"):
        return a + (b - a) * t


def lerp_clip(a, b, t):
    with tf.name_scope("lerp_clip"):
        return a + (b - a) * tf.clip_by_value(t, 0., 1.)


def gaussian_noise(x, std=5e-2):
    noise = tf.random_normal(x.get_shape(), mean=0., stddev=std, dtype=tf.float32)
    return x + noise


# ---------------------------------------------------------------------------------------------
# Optimizer

class Optimizer(object):

    def __init__(self,
                 name='train',
                 optimizer='tf.train.AdamOptimizer',
                 learning_rate=1e-3,
                 use_loss_scaling=False,
                 loss_scaling_init=64.,
                 loss_scaling_inc=5e-4,
                 loss_scaling_dec=1.,
                 use_grad_scaling=False,
                 grad_scaling=7.,
                 **kwargs):

        self.name = name
        self.optimizer = optimizer
        self.learning_rate = learning_rate

        self.use_loss_scaling = use_loss_scaling
        self.loss_scaling_init = loss_scaling_init
        self.loss_scaling_inc = loss_scaling_inc
        self.loss_scaling_dec = loss_scaling_dec

        self.use_grad_scaling = use_grad_scaling
        self.grad_scaling = grad_scaling


# ---------------------------------------------------------------------------------------------
# Network

class Network:

    def __init__(self):
        pass


# ---------------------------------------------------------------------------------------------
# Functions

w_init = tf.contrib.layers.variance_scaling_initializer(factor=1., mode='FAN_AVG', uniform=True)
b_init = tf.zeros_initializer()

reg = 5e-4
w_reg = tf.contrib.layers.l2_regularizer(reg)

eps = 1e-5


# Layers

def conv2d(x, f=64, k=3, s=1, pad='SAME', name='conv2d'):
    """
    :param x: input
    :param f: filters
    :param k: kernel size
    :param s: strides
    :param pad: padding
    :param name: scope name
    :return: net
    """
    return tf.layers.conv2d(inputs=x,
                            filters=f, kernel_size=k, strides=s,
                            kernel_initializer=w_init,
                            kernel_regularizer=w_reg,
                            bias_initializer=b_init,
                            padding=pad,
                            name=name)


def sub_pixel_conv2d(x, f, s=2):
    """
    # ref : https://github.com/tensorlayer/SRGAN/blob/master/tensorlayer/layers.py
    """
    if f is None:
        f = int(int(x.get_shape()[-1]) / (s ** 2))

    bsize, a, b, c = x.get_shape().as_list()
    bsize = tf.shape(x)[0]

    x_s = tf.split(x, s, 3)
    x_r = tf.concat(x_s, 2)

    return tf.reshape(x_r, (bsize, s * a, s * b, f))


def deconv2d(x, f=64, k=3, s=1, pad='SAME', name='deconv2d'):
    """
    :param x: input
    :param f: filters
    :param k: kernel size
    :param s: strides
    :param pad: padding
    :param name: scope name
    :return: net
    """
    return tf.layers.conv2d_transpose(inputs=x,
                                      filters=f, kernel_size=k, strides=s,
                                      kernel_initializer=w_init,
                                      kernel_regularizer=w_reg,
                                      bias_initializer=b_init,
                                      padding=pad,
                                      name=name)


def dense(x, f=1024, name='fc'):
    """
    :param x: input
    :param f: fully connected units
    :param name: scope name
    :return: net
    """
    return tf.layers.dense(inputs=x,
                           units=f,
                           kernel_initializer=w_init,
                           kernel_regularizer=w_reg,
                           bias_initializer=b_init,
                           name=name)


# Normalize

def batch_norm(x, momentum=0.9, scaling=True, is_train=True):
    return tf.layers.batch_normalization(inputs=x,
                                         momentum=momentum,
                                         epsilon=eps,
                                         scale=scaling,
                                         training=is_train)


def instance_norm(x, affine=True, name=""):
    with tf.variable_scope('instance_normalize-%s' % name):
        mean, variance = tf.nn.moments(x, [1, 2], keep_dims=True)

        normalized = tf.div(x - mean, tf.sqrt(variance + eps))

        if not affine:
            return normalized
        else:
            depth = x.get_shape()[3]  # input channel

            scale = tf.get_variable('scale', [depth],
                                    initializer=tf.random_normal_initializer(mean=1., stddev=.02, dtype=tf.float32))
            offset = tf.get_variable('offset', [depth],
                                     initializer=tf.zeros_initializer())

        return scale * normalized + offset


# Activations

def prelu(x, stddev=1e-2, reuse=False, name='prelu'):
    with tf.variable_scope(name):
        if reuse:
            tf.get_variable_scope().reuse_variables()

        _alpha = tf.get_variable('_alpha',
                                 shape=x.get_shape(),
                                 initializer=tf.constant_initializer(stddev),
                                 dtype=x.dtype)

        return tf.maximum(_alpha * x, x)


# Losses

def l1_loss(x, y):
    return tf.reduce_mean(tf.abs(x - y))


def mse_loss(x, y):  # l2_loss
    return tf.reduce_mean(tf.squared_difference(x=x, y=y))


def rmse_loss(x, y):
    return tf.sqrt(mse_loss(x, y))


def psnr_loss(x, y):
    return 20. * tf.log(tf.reduce_max(x) / mse_loss(x, y))


def sce_loss(data, label):
    return tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=data, labels=label))


def softce_loss(data, label):
    return tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(logits=data, labels=label))
