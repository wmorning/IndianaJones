import numpy as np
import inDianajonES as InD
import tensorflow as tf


'''
ConvNNet implements a convolutional neural network 
using the TensorFlow framework. It consists of a 
ConvNNet class, which contains several functions:
    
    - Train inputs a list of images and artifacts,
        builds the design matrix, and implements
        the neural net (outputting the training)
        error as it goes
    
    - Test runs the neural net on a test data set.
        Can do whatever we make it do.
    
    - Save_model saves the session to the input filename.
    
    - Resume_from loads a saved session.
    
Also @Joe if you are wondering why I used a class, its 
because the class allowed the session to be saved as a 
global variable without it being a script.
'''

# ============================================================

class ConvNNet(object):
    '''
    ConvNNet implements a convolutional neural network 
    using the TensorFlow framework.
    '''
    def __init__(self):
        
        self.runs = None
        self.expids = None
        self.artifacts = None
        self.Nsteps = None
        
        return
    
    def Train(self, runs , expids , artifacts , Nsteps , gridsize=128 , cgfactor=8 , load_data=True):
        '''
        This function creates the design matrix and loads the
        true clasifications (if they don't already exist).  
        It then runs the neural net to train the optimal 
        predicting scheme.
        
        * Currently the neural net is very similar to the
        one used in the MNIST tutorial from Tensorflow (except
        modified to use our images etc.).  We 
        should modify it further to fit our needs *
        
        Function inputs are below:
    
        - runs is the run info of the training data
    
        - expids are the exposure ids of the training data
    
        - artifacts is list of artifact objects (preprocessed)
    
        - Nsteps is number of training steps to run
    
        - gridsize is size (in pixels) of the postage stamps.
        * Note:  must be evenly divisible into 2048 *
        
        - cgfactor is coarse-graining factor.
        * Note:  must be evenly divisibile into gridsize *
        '''
        
        if load_data is True: # if false, must have X, ey, and ey2 loaded in mem.
            assert 2048 % self.gridsize == 0
            self.gridsize = gridsize
            assert (self.gridsize//self.cgfactor)%4 == 0
            self.cgfactor = cgfactor
        

            # load/make training data:  @Joe: edit as needed.  In particular
            # we want X to have shape [Nexamples, Npixels], and y to 
            # have shape [Nexamples , Ncategories] and be all zeros 
            # along the second axis (except for the correct classification),
            # which is a 1.  This is what ey2 is.
            imagenames, bkgnames = get_training_filenames(runs,expids)
            X , Y = create_design_matrix(imagenames , bkgnames , artifacts , gridsize , cgfactor)
            ey = enumerate_labels(Y)
     
            ey2 = np.zeros([len(ey),int(np.max(ey))+1],float)
            for i in range(len(ey)):
                ey2[i,ey[i]-1] = 1.0
    
    
        # Ncategories is number of classifications
        Ncategories = int(np.max(ey))+1
        Nexamples = len(ey)
        
        # start neural net: define x,y placeholders and create session
        self.Session = tf.InteractiveSession()  # useful if running from notebook
        x = tf.placeholder("float",shape=[None,gridsize**2])
        x_image = tf.reshape(x,[-1,gridsize,gridsize,1])    
        y_ = tf.placeholder("float",shape=[None,Ncategories])
    
        # create first layer
        # here we create 32 new images using a convolution with a
        # 5x5x32 weights filter plus a bias (one for each new image)
        W_conv1 = weight_variable([5,5,1,32])  # play around with altering sizes
        b_conv1 = bias_variable([32])# length should be same as last dimension of W_conv1
        h_conv1 = tf.nn.relu(conv2d(x_image, W_conv1)+b_conv1)
        # split each image into 4, and obtain the maximum quadrant
        h_pool1 = max_pool_2x2(h_conv1)
    
        # create second layer
        # here each of our 32 intermediate images is convolved with
        # a 5x5x64 weights filter.  We create 64 new images by summing
        # over all 32 convolutions.  Each of the 64 images has its own bias
        # term.  The shape of the result is the shape of the original image 
        # divided by 4 on each axis by 64 (i.e. if you started with a 
        # 2048x2048 image, you now have a 512x512x64 image)
        W_conv2 = weight_variable([5,5,32,64]) # again, play with altering sizes
        b_conv2 = bias_variable([64])          # of the first two axes
        h_conv2 = tf.nn.relu(conv2d(h_pool1, W_conv2) + b_conv2)
        # split each image into 4, and obtain the maximum quadrant
        h_pool2 = max_pool_2x2(h_conv2)
    
        # Densely Connected layer
        # Here, the 7x7x64 image tensor is flattened, and we get a 
        # 1x1024 vector using the form h_fc1 = h_2 * W + b
        W_fc1 = weight_variable([(self.gridsize//4)*(self.gridsize//4)*64, 1024])
        b_fc1 = bias_variable([1024])
        h_pool2_flat = tf.reshape(h_pool2, [-1, \
                                  (self.gridsize//self.cgfactor//4) \
                                  *(self.gridsize//self.cgfactor//4)*64])
        h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1)+b_fc1)
    
        # avoid overfitting using tensorflows dropout function.
        # specifically, we keep each component of h_fc1 with
        # probability keep_prob.
        keep_prob = tf.placeholder("float")
        h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)
    
        # finally, a softmax regression to predict the output
        W_fc2 = weight_variable([1024,Ncategories])
        b_fc2 = bias_variable([Ncategories])
    
        # output of NN
        y_conv = tf.nn.softmax(tf.matmul(h_fc1_drop, W_fc2) + b_fc2)
    
        # run the optimization.  We'll minimize the cross entropy
        cross_entropy = -tf.reduce_sum(y_*tf.log(y_conv))
        train_step = tf.train.AdamOptimizer(1e-4).minimize(cross_entropy)
        correct_prediction = tf.equal(tf.argmax(y_conv,1), tf.argmax(y_,1))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction,"float"))
        self.Session.run(tf.initialize_all_variables())
        
        # batch gradient descent ticker
        current_index = 0
        for i in range(Nsteps):
            # update the parameters using batch gradient descent.
            # use 50 examples per iteration (can change)
            next_set = [(current_index+i) % Nexamples for i in range(50)]
            x_examples = X[next_set,:]
            y_examples = ey2[next_set,:]
            current_index = (current_index+50) % Nexamples
        
            #for every thousandth step, print the training error.
            if i%1000 ==0:
                train_accuracy = accuracy.eval(feed_dict={x:x_examples \
                             , y_: y_examples, keep_prob: 1.0})
                print "step %d, training accuracy %g"%(i, train_accuracy)
        
            train_step.run(feed_dict={x: x_examples, y_: y_examples, keep_prob: 0.5})
    
    
        return
    
    
    def Test(self,test_data):
        raise Exception('cannot test model yet \n')
        return
        
    def Save_model(self, filename):
        '''
        Use tensorflow's train.Saver to create checkpoint
        file.
        '''
        raise Exception('cannot save model yet \n')
        saver = tf.train.Saver()
        saver.save(self.Session, filename, global_step=step)
        return
    
    def Resume_from(self, filename):
        '''
        Use tensorflow's train.Saver to reload a saved
        checkpoint, and resume training.
        '''
        raise Exception('cannot resume training yet \n')
        saver = tf.train.Saver()
        saver.restore(self.Session, filename)
        return
        
# ------------------------------------------------------------   
'''
Neural net functions
'''
def weight_variable(shape):
    '''
    Initialize a tensorflow weight variable
    '''
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial) # note: this won't let us spread across multiple GPUs.

def bias_variable(shape):
    '''
    Initialize a tensorflow bias variable
    '''
    initial = tf.constant(0.1,shape=shape)
    return tf.Variable(initial)

def conv2d(x,W):
    '''
    Convolve a 2d image (x) with a filter (W)
    '''
    return tf.nn.conv2d(x, W, strides=[1,1,1,1], padding='SAME')

def max_pool_2x2(x):
    '''
    Return quadrant of image with max pixel values
    '''
    return tf.nn.max_pool(x, ksize=[1,2,2,1], strides=[1,2,2,1], padding='SAME')

# ------------------------------------------------------------