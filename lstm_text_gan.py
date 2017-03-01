
from __future__ import print_function
from keras.utils.data_utils import get_file
# from keras import backend as K
import numpy as np
import random
import sys

# from tensorflow_boilerplate import *
import canton as ct
import tensorflow as tf

zed = 32
time_steps = 1024

def char2eight(n):
    binary = "{0:b}".format(n)
    rep = np.zeros((8,),dtype='float32')
    for i in range(len(binary)): # 0..2
        rep[i+8-len(binary)] = 1 if binary[i] == '1' else 0
    return rep

def eight2char(e):
    out = 0
    for i in range(len(e)):
        out += (1 if e[7-i]>0.5 else 0) * 2**i
    return int(out)

def one_hot(tensor,dims):
    onehot = np.zeros((len(tensor),dims),dtype='float32')
    for i in range(dims):
        onehot[...,i] = tensor[...] == i
    return onehot

def one_hot_int(integer, dims):
    h = np.zeros((1,dims),dtype='float32')
    h[:,integer] = 1
    return h

def to_asc(text):
    asc = np.zeros((len(text),),dtype='uint8')
    # convert into ascii
    for i in range(len(text)):
        asc[i] = ord(text[i])
    return asc

def textdata():
    path = get_file('nietzsche.txt', origin="https://s3.amazonaws.com/text-datasets/nietzsche.txt")
    text = open(path).read()
    length = len(text)
    print('got corpus length:', length)

    # convert into ascii
    asc = to_asc(text)

    # convert into 8dim
    # for i in range(length):
    #     onehot[i] = char2eight(asc[i])

    # convert into onehot
    onehot = one_hot(asc,256)

    return text,onehot

text,corpus = textdata()
print('corpus loaded. corpus[0]:',corpus[0])

def mymodel_builder():
    can = ct.Can()
    gru,d1,d2 = ct.GRU(256,256),ct.TimeDistributedDense(256,64),ct.TimeDistributedDense(64,256)
    can.incan([gru,d1,d2])
    def call(i,starting_state=None):
        i = gru(i,starting_state=starting_state)
        # (batch, time_steps, 512)
        shape = tf.shape(i)
        b,t,d = shape[0],shape[1],shape[2]
        ending_state = i[:,t-1,:]

        i = d1(i)
        i = tf.nn.elu(i)
        i = d2(i)

        if starting_state is None:
            return i
        else:
            return i, ending_state
    can.set_function(call)
    return can

mymodel = mymodel_builder()

def feed_gen():
    x = tf.placeholder(tf.float32, shape=[None, None, corpus.shape[1]])
    y = mymodel(x)
    gt = tf.placeholder(tf.float32, shape=[None, None, corpus.shape[1]])
    loss = ct.mean_softmax_cross_entropy(y,gt)

    train_step = tf.train.AdamOptimizer(1e-3).minimize(
        loss,var_list=mymodel.get_weights())

    def feed(minibatch,labels):
        nonlocal train_step,loss,x,gt
        sess = ct.get_session()
        res = sess.run([loss,train_step],feed_dict={x:minibatch,gt:labels})
        return res[0]

    starting_state = tf.placeholder(tf.float32, shape=[None, None])
    stateful_y, ending_state = mymodel(x,starting_state=starting_state)

    def predict(st,i):
        # stateful, to enable fast generation.
        sess = ct.get_session()
        res = sess.run([stateful_y,ending_state],feed_dict={x:i,starting_state:st})
        return res

    return feed,predict

feed,predict = feed_gen()

sess = ct.get_session()
sess.run(tf.variables_initializer(mymodel.get_weights()))
sess.run(tf.global_variables_initializer())

def r(ep=100):
    length = len(corpus)
    batch_size = 1
    mbl = time_steps * batch_size
    sr = length - mbl - time_steps - 2
    for i in range(ep):
        print('---------------------iter',i,'/',ep)

        j = np.random.choice(sr)

        minibatch = corpus[j:j+mbl]
        minibatch.shape = [batch_size, time_steps, corpus.shape[1]]
        labels = corpus[j+1:j+mbl+1]
        labels.shape = [batch_size,time_steps,corpus.shape[1]]

        loss = feed(minibatch,labels)
        print('loss:',loss)

        if i%100==0 : pass#show2()

def softmax(x):
    scoreMatExp = np.exp(np.asarray(x))
    return scoreMatExp / scoreMatExp.sum(0)

import sys
def show2(length=400):
    t = 97
    starting_state = np.zeros((1,256),dtype='float32')
    for i in range(length):
        # convert into ascii
        # asc = to_asc(t[-time_steps:])
        asc = t
        hot = one_hot_int(asc,256)
        hot.shape = (1,)+hot.shape
        #print(hot.shape)

        [stateful_y,ending_state] = predict(starting_state,hot)
        starting_state = ending_state

        res = stateful_y[0,0] # choose the last dimension
        dist = softmax(res) # do the softmath
        dist = (dist - np.mean(dist) > 0) * dist # pick the greater ones
        dist = dist / np.sum(dist) # normalize sum to 1
        code = np.random.choice(256, p=dist)
        # code = np.argmax(dist)

        #print(code)
        char = chr(code)
        t=code

        sys.stdout.write( '%s' % char )
        if i%10==0 : sys.stdout.flush()
    sys.stdout.flush()
    print('')
