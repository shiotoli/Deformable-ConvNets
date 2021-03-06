# --------------------------------------------------------
# Deformable Convolutional Networks
# Copyright (c) 2016 by Contributors
# Copyright (c) 2017 Microsoft
# Licensed under The Apache-2.0 License [see LICENSE for details]
# Written by Zheng Zhang
# --------------------------------------------------------

# --------------------------------------------------------

# Modified By DeepInsight

#  0. Todo: Make Code Tidier (with exec)
#  1. Todo: ResNeXt v2 : Grouping + Pre-Activation
#  2. Todo: IRB: First Block of Inception-ResNet , with Grouping
#  3. Todo: DeepLab v3, with multiple dilation pattern options
#  4. Todo: Dual Path Network ( DenseNet + ResNeXt Nx4d)

# --------------------------------------------------------


import cPickle
import mxnet as mx
from utils.symbol import Symbol


###### UNIT LIST #######

# Todo 1,2,4

def irnext_unit(data, num_filter, stride, dim_match, name, bottle_neck=1, expansion=0.5, \
                 num_group=32, dilation=1, irv2 = False, deform=0, bn_mom=0.9, workspace=256, memonger=False):
    
    """
    Return Unit symbol for building ResNeXt/simplified Xception block
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    stride : int
        Number of stride, 2 when block-crossing with downsampling or simple downsampling, else 1.
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name: str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    bottle_neck : int = 0,1,2,3
        If 0: Use conventional Conv3,3-Conv3,3
        If 1: Use ResNeXt Conv1,1-Conv3,3-Conv1,1
        If 2: Use IRB use Conv1,1-[Conv3,3;Conv3,3-Conv3,3]-Conv1,1
        If 3: Use Dual-Path-Net
    irv2: Boolean 
        if True: IRB use pre-activation
        if False: IRB do not use pre-activation
        
    expansion : float
        ResNet use 4, ResNeXt use 2, DenseNet use 0.25
    num_group: int
        Feasible Range: 4,8,16,32,64
    dilation: int
        a.k.a Atrous Convolution
    deform: 
        Deformable Conv Net
    """
    
    ## If 0: Use conventional Conv3,3-Conv3,3
    if bottle_neck == 0 :
        
        conv1 = mx.sym.Convolution(data=data, num_filter=num_filter, kernel=(3,3), stride=stride, 
                                   pad=(dilation,dilation), dilate=(dilation,dilation), 
                                   no_bias=True, workspace=workspace, name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1, fix_gamma=False, momentum=bn_mom, eps=2e-5, name=name + '_bn1')
        act1 = mx.sym.Activation(data=bn1, act_type='relu', name=name + '_relu1')

        
        conv2 = mx.sym.Convolution(data=act1, num_filter=num_filter, kernel=(3,3), stride=(1,1),
                                   pad=(dilation,dilation), dilate=(dilation,dilation)
                                      no_bias=True, workspace=workspace, name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2, fix_gamma=False, momentum=bn_mom, eps=2e-5, name=name + '_bn2')

        if dim_match:
            shortcut = data
        else:
            shortcut_conv = mx.sym.Convolution(data=data, num_filter=num_filter, kernel=(1,1), stride=stride, no_bias=True,
                                            workspace=workspace, name=name+'_sc')
            shortcut = mx.sym.BatchNorm(data=shortcut_conv, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_sc_bn')

        if memonger:
            shortcut._set_attr(mirror_stage='True')
            
        eltwise = bn2 + shortcut
        
        return mx.sym.Activation(data=eltwise, act_type='relu', name=name + '_relu')
    
    # If 1: Use ResNeXt Conv1,1-Conv3,3-Conv1,1 
    elif bottle_neck == 1:
        
        # the same as https://github.com/facebook/fb.resnet.torch#notes, a bit difference with origin paper
        
        conv1 = mx.sym.Convolution(data=data, num_filter=int(num_filter/expansion), kernel=(1,1), stride=(1,1), pad=(0,0),
                                      no_bias=True, workspace=workspace, name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn1')
        act1 = mx.sym.Activation(data=bn1, act_type='relu', name=name + '_relu1')

        
        conv2 = mx.sym.Convolution(data=act1, num_filter=int(num_filter/expansion), 
                                   num_group=num_group, kernel=(3,3), stride=stride, 
                                   pad=(dilation,dilation), dilate=(dilation,dilation),
                                   no_bias=True, workspace=workspace, name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn2')
        act2 = mx.sym.Activation(data=bn2, act_type='relu', name=name + '_relu2')

        
        conv3 = mx.sym.Convolution(data=act2, num_filter=num_filter, kernel=(1,1), stride=(1,1), pad=(0,0), no_bias=True,
                                   workspace=workspace, name=name + '_conv3')
        bn3 = mx.sym.BatchNorm(data=conv3, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn3')

        if dim_match:
            shortcut = data
        else:
            shortcut_conv = mx.sym.Convolution(data=data, num_filter=num_filter, kernel=(1,1), stride=stride, no_bias=True,
                                            workspace=workspace, name=name+'_sc')
            shortcut = mx.sym.BatchNorm(data=shortcut_conv, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_sc_bn')

        if memonger:
            shortcut._set_attr(mirror_stage='True')
        eltwise =  bn3 + shortcut
        return mx.sym.Activation(data=eltwise, act_type='relu', name=name + '_relu')
    
    
    elif bottle_neck == 2:
        # Left Branch
        conv11 = mx.sym.Convolution(data=data, num_filter=int(num_filter/expansion), kernel=(1,1), stride=(1,1), pad=(0,0),
                                      no_bias=True, workspace=workspace, name=name + '_conv11')
        bn11 = mx.sym.BatchNorm(data=conv11, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn11')
        act11 = mx.sym.Activation(data=bn11, act_type='relu', name=name + '_relu11')

        
        conv12 = mx.sym.Convolution(data=act11, num_filter=int(num_filter/expansion), 
                                   num_group=num_group, kernel=(3,3), stride=stride, 
                                   pad=(dilation,dilation), dilate=(dilation,dilation),
                                   no_bias=True, workspace=workspace, name=name + '_conv12')
        
        # Right Branch
        conv21 = mx.sym.Convolution(data=data, num_filter=int(num_filter/expansion/2), kernel=(1,1), stride=(1,1), pad=(0,0),
                                      no_bias=True, workspace=workspace, name=name + '_conv21')
        bn21 = mx.sym.BatchNorm(data=conv21, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn21')
        act21 = mx.sym.Activation(data=bn21, act_type='relu', name=name + '_relu21')

        
        conv22 = mx.sym.Convolution(data=act21, num_filter=int(num_filter/expansion/2), 
                                   num_group=num_group, kernel=(3,3), stride=stride, 
                                   pad=(dilation,dilation), dilate=(dilation,dilation),
                                   no_bias=True, workspace=workspace, name=name + '_conv22')
        
        bn22 = mx.sym.BatchNorm(data=conv22, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn22')
        act22 = mx.sym.Activation(data=bn22, act_type='relu', name=name + '_relu22')
        
        # Consecutive Conv(3,3) Use  stride=(1,1) instead of stride=(3,3)
        conv23 = mx.sym.Convolution(data=act22, num_filter=int(num_filter/expansion/2), 
                                   num_group=num_group, kernel=(3,3), stride=(1,1), 
                                   pad=(dilation,dilation), dilate=(dilation,dilation),
                                   no_bias=True, workspace=workspace, name=name + '_conv23')
        
        conv2 = mx.symbol.Concat(*[conv12, conv23])
        
        bn30 = mx.sym.BatchNorm(data=conv2, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn30')
        act30 = mx.sym.Activation(data=bn30, act_type='relu', name=name + '_relu30')
        
        conv31 = mx.sym.Convolution(data=act30, num_filter=num_filter, kernel=(1,1), stride=(1,1), pad=(0,0),
                                      no_bias=True, workspace=workspace, name=name + '_conv31')
        
        bn31 = mx.sym.BatchNorm(data=conv31, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn31')
        # Original Paper: With act31
        act31 = mx.sym.Activation(data=bn31, act_type='relu', name=name + '_relu31')
        
        
        if dim_match:
            shortcut = data
        else:
            shortcut_conv = mx.sym.Convolution(data=data, num_filter=num_filter, kernel=(1,1), stride=stride, no_bias=True,
                                            workspace=workspace, name=name+'_sc')
            shortcut = mx.sym.BatchNorm(data=shortcut_conv, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_sc_bn')

        if memonger:
            shortcut._set_attr(mirror_stage='True')
        # Original Paper : act31+shortcut, else bn31 + shortcut
        if irv2: 
            eltwise =  bn31 + shortcut
        else :
            eltwise =  act31 + shortcut
        
        return mx.sym.Activation(data=eltwise, act_type='relu', name=name + '_relu')
    
    
    elif bottle_neck == 3:
         # TODO
        raise Exception("bottle_neck error: Unimplemented Bottleneck Unit: Dual Path Net.")
         
    else:
        raise Exception("bottle_neck error: Unrecognized Bottleneck params.")


        
def irnext(units, num_stages, filter_list, num_classes, num_group, bottle_neck=1, \
               lastout = 7, expansion = 0.5, dilpat = '', irv2 = False,  deform = 0, taskmode='CLS',
           seg_stride_list = [1,2,2,1],
           bn_mom=0.9, workspace=256, dtype='float32', memonger=False):
    """Return ResNeXt symbol of
    Parameters
    ----------
    units : list
        Number of units in each stage
    num_stages : int
        Number of stage
    filter_list : list
        Channel size of each stage
    num_classes : int
        Number of Classes, 1k/5k/11k/22k/etc
    num_groups: int
        Same as irnext unit
    bottle_neck: int=0,1,2,3
        Same as irnext unit
    lastout: int
        Size of last Conv
        Original Image Size Should Be: 3,(32*lastout),(32*lastout)
    expansion: float
        Same as irnext unit
    dilpat: str
        Best Practice: DEEPLAB.SHUTTLE
        '': (1,1,1)
        DEEPLAB.SHUTTLE: (1,2,1)
        DEEPLAB.HOURGLASS: (2,1,2)
        DEEPLAB.LIN: (1,2,3)
        DEEPLAB.REVLIN: (3,2,1)
        DEEPLAB.DOUBLE: (2,2,2)
        DEEPLAB.EXP: (1,2,4)
        DEEPLAB.REVEXP: (4,2,1)
    deform: int
        Use DCN
    taskmode: str
        'CLS': Classification
        'Seg': Segmentation
    dataset : str
        Dataset type, only cifar10 and imagenet supports
    workspace : int
        Workspace used in convolution operator
    dtype : str
        Precision (float32 or float16)
    """

    num_unit = len(units)
    assert(num_unit == num_stages)
    data = mx.sym.Variable(name='data')
    if dtype == 'float32':
        data = mx.sym.identity(data=data, name='id')
    else:
        if dtype == 'float16':
            data = mx.sym.Cast(data=data, dtype=np.float16)
    
    data = mx.sym.BatchNorm(data=data, fix_gamma=True, eps=2e-5, momentum=bn_mom, name='bn_data')
    
    (nchannel, height, width) = (3, lastout*32, lastout*32)
    
    
    
    if height <= 32:            # such as cifar10/cifar100
        body = mx.sym.Convolution(data=data, num_filter=filter_list[0], kernel=(3, 3), stride=(1,1), pad=(1, 1),
                                  no_bias=True, name="conv0", workspace=workspace)
    else:                       # often expected to be 224 such as imagenet
        body = mx.sym.Convolution(data=data, num_filter=filter_list[0], kernel=(7, 7), stride=(2,2), pad=(3, 3),
                                  no_bias=True, name="conv0", workspace=workspace)
        body = mx.sym.BatchNorm(data=body, fix_gamma=False, eps=2e-5, momentum=bn_mom, name='bn0')
        body = mx.sym.Activation(data=body, act_type='relu', name='relu0')
        body = mx.sym.Pooling(data=body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')

        
    # Unit Params List:
    # data, num_filter, stride, dim_match, name, bottle_neck=1, expansion=0.5, \
    # num_group=32, dilation=1, irv2 = False, deform=0, 
    
    dilation_dict = {'DEEPLAB.SHUTTLE':[1,1,2,1],
                    'DEEPLAB.HOURGLASS':[1,2,1,2],
                    'DEEPLAB.EXP':[1,1,2,4],
                    'DEEPLAB.REVEXP':[1,4,2,1],
                    'DEEPLAB.LIN':[1,1,2,3]
                    'DEEPLAB.REVLIN':[1,3,2,1],
                    'DEEPLAB.DOUBLE':[1,2,2,2]}
    
    
    
    if taskmode == 'CLS':
        stride_plan = [1,2,2,2]
        dilation_plan = [1,1,1,1] if dilpat not in dilation_dict else dilation_dict[dilpat]
        
        for i in range(num_stages):
            body = irnext_unit(body, filter_list[i+1], (stride_plan[i], stride_plan[i]), False,
                             name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, 
                             expansion = expansion, num_group=num_group, dilate = (dilation_plan[i],dilation_plan[i]),
                             irv2 = irv2, deform = deform
                             bn_mom=bn_mom, workspace=workspace, memonger=memonger)
            for j in range(units[i]-1):
                body = irnext_unit(body, filter_list[i+1], (1,1), True, name='stage%d_unit%d' % (i + 1, j + 2),
                                 bottle_neck=bottle_neck, expansion = expansion, num_group=num_group, 
                                 dilate = (dilation_plan[i],dilation_plan[i]), irv2 = irv2, deform = deform ,
                                 bn_mom=bn_mom, workspace=workspace, memonger=memonger)
            
        pool1 = mx.sym.Pooling(data=body, global_pool=True, kernel=(lastout, lastout), pool_type='avg', name='pool1')
        flat = mx.sym.Flatten(data=pool1)
        fc1 = mx.sym.FullyConnected(data=flat, num_hidden=num_classes, name='fc1')
        if dtype == 'float16':
            fc1 = mx.sym.Cast(data=fc1, dtype=np.float32)
        return mx.sym.SoftmaxOutput(data=fc1, name='softmax')
    
    
    elif taskmode == 'SEG':
        
        # Deeplab Without Deform
        # Deeplab With Deform
        # Deeplab v1 Use Stride_List = [1,2,2,1] So a 16x Deconv Needed
        # Deeplab v2/v3 Use Stride_List = [1,2,1,1] So 1/8 gt and 1/8 img compute loss
        # Pytorch-Deeplab Use 1x+0.707x+0.5x Multi-Scale Shared Params Trick
        stride_plan = seg_stride_plan
        dilation_plan = [1,1,1,1] if dilpat not in dilation_dict else dilation_dict[dilpat]
        
        for i in range(num_stages):
            body = irnext_unit(body, filter_list[i+1], (stride_plan[i], stride_plan[i]), False,
                             name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, 
                             expansion = expansion, num_group=num_group, dilate = (dilation_plan[i],dilation_plan[i]),
                             irv2 = irv2, deform = deform
                             bn_mom=bn_mom, workspace=workspace, memonger=memonger)
            for j in range(units[i]-1):
                body = irnext_unit(body, filter_list[i+1], (1,1), True, name='stage%d_unit%d' % (i + 1, j + 2),
                                 bottle_neck=bottle_neck, expansion = expansion, num_group=num_group, 
                                 dilate = (dilation_plan[i],dilation_plan[i]), irv2 = irv2, deform = deform ,
                                 bn_mom=bn_mom, workspace=workspace, memonger=memonger)
                
        return body
        

def get_symbol(num_classes, num_layers, outfeature, bottle_neck=1, expansion=0.5,
               num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
               taskmode='CLS', seg_stride_mode='', dtype='float32', **kwargs):
    """
    Adapted from https://github.com/tornadomeet/ResNet/blob/master/train_resnet.py
    Original author Wei Wu
    """
    
    # Model Params List:
    # num_classes, num_layers, bottle_neck=1, expansion=0.5, \
    # num_group=32, dilation=1, irv2 = False, deform=0, taskmode, seg_stride_mode
    
    (nchannel, height, width) = (3, 32* lastout, 32*lastout)
    
    
    if height <= 32: # CIFAR10/CIFAR100
        num_stages = 3
        if (num_layers-2) % 9 == 0 and num_layers >= 164:
            per_unit = [(num_layers-2)//9]
            filter_list = [16, int(outfeature/4), int(outfeature/2), outfeature]
            use_bottle_neck = bottle_neck
            
        elif (num_layers-2) % 6 == 0 and num_layers < 164:
            per_unit = [(num_layers-2)//6]
            filter_list = [16, int(outfeature/4), int(outfeature/2), outfeature]
            use_bottle_neck = 0
        else:
            raise ValueError("no experiments done on num_layers {}, you can do it yourself".format(num_layers))
        
        units = per_unit * num_stages
        
    else:
        if num_layers >= 38:
            filter_list = [64, int(outfeature/8) , int(outfeature/4), int(outfeature/2), outfeature ]
            use_bottle_neck = bottle_neck
        else:
            filter_list = [64, int(outfeature/8) , int(outfeature/4), int(outfeature/2), outfeature ]
            use_bottle_neck = 0
            
        num_stages = 4
        if num_layers == 18:
            units = [2, 2, 2, 2]
        elif num_layers == 34:
            units = [3, 4, 6, 3]
        elif num_layers == 38:
            units = [3, 3, 3, 3]
        elif num_layers == 50:
            units = [3, 4, 6, 3]
        elif num_layers == 80:
            units = [3, 8, 12, 3]
        elif num_layers == 101:
            units = [3, 4, 23, 3]
        elif num_layers == 152:
            units = [3, 8, 36, 3]
        elif num_layers == 200:
            units = [3, 24, 36, 3]
        elif num_layers == 269:
            units = [3, 30, 48, 8]
        else:
            raise ValueError("no experiments done on num_layers {}, you can do it yourself".format(num_layers))

    if seg_stride_mode == '4x':
        seg_stride_list = [1,1,1,1]
    elif seg_stride_mode == '8x':
        seg_stride_list = [1,2,1,1]
    elif seg_stride_mode == '16x':
        seg_stride_list = [1,2,2,1]
    else:
        seg_stride_list = [1,2,2,1]
        
    
    return irnext(units       = units,
                  num_stages  = num_stages,
                  filter_list = filter_list,
                  num_classes = num_classes,
                  num_group   = num_group, 
                  bottle_neck = use_bottle_neck,
                  lastout     = lastout,
                  expansion   = expansion,
                  dilpat      = dilpat, 
                  irv2        = irv2,
                  deform      = deform, 
                  taskmode    = taskmode,
                  seg_stride_list = seg_stride_list,
                  workspace   = conv_workspace,
                  dtype       = dtype)
        
#### Original Deeplab DCN
        
        
        
# Todo 0 & 3 .


class irnext_deeplab_dcn(Symbol):
    
    
    def __init__(self, numclasses , num_layers , outfeature, bottle_neck=1, expansion=0.5,\
                num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
                taskmode='SEG', seg_stride_mode='', dtype='float32', **kwargs):
        """
        Use __init__ to define parameter network needs
        """
        self.eps = 1e-5
        self.use_global_stats = True
        self.workspace = 4096
        self.units = (3, 4, 23, 3) # use for 101
        self.filter_list = [256, 512, 1024, 2048]

    def get_cls_conv(self, data, num_classes, num_layers, outfeature, bottle_neck=1, expansion=0.5,
               num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
               dtype='float32', **kwargs):
        
        return get_symbol(num_classes, num_layers, outfeature, bottle_neck=1, expansion=0.5,
               num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
               taskmode='SEG', seg_stride_mode='', dtype='float32', **kwargs)
        
        
    def get_seg_conv(self, data, num_classes, num_layers, outfeature, bottle_neck=1, expansion=0.5,
               num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
               taskmode='SEG', seg_stride_mode='', dtype='float32', **kwargs):
        
        return get_symbol(num_classes, num_layers, outfeature, bottle_neck=1, expansion=0.5,
               num_group=32, lastout=7, dilpat='', irv2=False, deform=0, conv_workspace=256,
               taskmode='SEG', seg_stride_mode='', dtype='float32', **kwargs)
        

    def get_train_symbol(self, num_classes):
        """
        get symbol for training
        :param num_classes: num of classes
        :return: the symbol for training
        """
        data = mx.symbol.Variable(name="data")
        seg_cls_gt = mx.symbol.Variable(name='label')

        # shared convolutional layers
        conv_feat = self.get_resnet_conv(data)

        # subsequent fc layers by haozhi
        fc6_bias = mx.symbol.Variable('fc6_bias', lr_mult=2.0)
        fc6_weight = mx.symbol.Variable('fc6_weight', lr_mult=1.0)

        fc6 = mx.symbol.Convolution(data=conv_feat, kernel=(1, 1), pad=(0, 0), num_filter=1024, name="fc6",
                                    bias=fc6_bias, weight=fc6_weight, workspace=self.workspace)
        relu_fc6 = mx.sym.Activation(data=fc6, act_type='relu', name='relu_fc6')

        score_bias = mx.symbol.Variable('score_bias', lr_mult=2.0)
        score_weight = mx.symbol.Variable('score_weight', lr_mult=1.0)

        score = mx.symbol.Convolution(data=relu_fc6, kernel=(1, 1), pad=(0, 0), num_filter=num_classes, name="score",
                                      bias=score_bias, weight=score_weight, workspace=self.workspace)

        upsampling = mx.symbol.Deconvolution(data=score, num_filter=num_classes, kernel=(32, 32), stride=(16, 16),
                                             num_group=num_classes, no_bias=True, name='upsampling',
                                             attr={'lr_mult': '0.0'}, workspace=self.workspace)
        
        ## DeepLab v2 Fix:
        '''
        score_0_bias = 
        score_0_weight = 
        score_0 = mx.symbol.Convolution(data= , kernel=(3,3), dilate=(dilate[0],dilate[0]), pad=(dilate[0],dilate[0]) )
        
        score = score0
        
        for i in range(1, len (final_dilate_list) ):
        
            exec'' score_i_bias = 
            exec'' score_i_weight = 
            exec'' score_i = mx.symbol.Convolution(data= , kernel=(3,3), \
                                                   dilate=(dilate[i],dilate[i]), pad=(dilate[i],dilate[i]) )
            score = score + score_i
            
        # Todo: Fix How to Upsampling?
        
        
        upsampling_v2 = mx.symbol.Deconvolution(data=score, num_filter=num_classes, kernel=(16, 16), stride=(16, 16),
                                             num_group=num_classes, no_bias=True, name='upsampling',
                                             attr={'lr_mult': '0.0'}, workspace=self.workspace)
        
        ### 
        
        '''
        
        
        
        
        
        
        


        croped_score = mx.symbol.Crop(*[upsampling, data], offset=(8, 8), name='croped_score')
        softmax = mx.symbol.SoftmaxOutput(data=croped_score, label=seg_cls_gt, normalization='valid', multi_output=True,
                                          use_ignore=True, ignore_label=255, name="softmax")

        return softmax

    def get_test_symbol(self, num_classes):
        """
        get symbol for testing
        :param num_classes: num of classes
        :return: the symbol for testing
        """
        data = mx.symbol.Variable(name="data")

        # shared convolutional layers
        conv_feat = self.get_resnet_conv(data)

        fc6_bias = mx.symbol.Variable('fc6_bias', lr_mult=2.0)
        fc6_weight = mx.symbol.Variable('fc6_weight', lr_mult=1.0)

        fc6 = mx.symbol.Convolution(
            data=conv_feat, kernel=(1, 1), pad=(0, 0), num_filter=1024, name="fc6", bias=fc6_bias, weight=fc6_weight,
            workspace=self.workspace)
        relu_fc6 = mx.sym.Activation(data=fc6, act_type='relu', name='relu_fc6')

        score_bias = mx.symbol.Variable('score_bias', lr_mult=2.0)
        score_weight = mx.symbol.Variable('score_weight', lr_mult=1.0)

        score = mx.symbol.Convolution(
            data=relu_fc6, kernel=(1, 1), pad=(0, 0), num_filter=num_classes, name="score", bias=score_bias,
            weight=score_weight, workspace=self.workspace)

        upsampling = mx.symbol.Deconvolution(
            data=score, num_filter=num_classes, kernel=(32, 32), stride=(16, 16), num_group=num_classes, no_bias=True,
            name='upsampling', attr={'lr_mult': '0.0'}, workspace=self.workspace)

        croped_score = mx.symbol.Crop(*[upsampling, data], offset=(8, 8), name='croped_score')

        softmax = mx.symbol.SoftmaxOutput(data=croped_score, normalization='valid', multi_output=True, use_ignore=True,
                                          ignore_label=255, name="softmax")

        return softmax

    def get_symbol(self, cfg, is_train=True):
        """
        return a generated symbol, it also need to be assigned to self.sym
        """

        # config alias for convenient
        num_classes = cfg.dataset.NUM_CLASSES

        if is_train:
            self.sym = self.get_train_symbol(num_classes=num_classes)
        else:
            self.sym = self.get_test_symbol(num_classes=num_classes)

        return self.sym

    def init_weights(self, cfg, arg_params, aux_params):
        arg_params['res5a_branch2b_offset_weight'] = mx.nd.zeros(shape=self.arg_shape_dict['res5a_branch2b_offset_weight'])
        arg_params['res5a_branch2b_offset_bias'] = mx.nd.zeros(shape=self.arg_shape_dict['res5a_branch2b_offset_bias'])
        arg_params['res5b_branch2b_offset_weight'] = mx.nd.zeros(shape=self.arg_shape_dict['res5b_branch2b_offset_weight'])
        arg_params['res5b_branch2b_offset_bias'] = mx.nd.zeros(shape=self.arg_shape_dict['res5b_branch2b_offset_bias'])
        arg_params['res5c_branch2b_offset_weight'] = mx.nd.zeros(shape=self.arg_shape_dict['res5c_branch2b_offset_weight'])
        arg_params['res5c_branch2b_offset_bias'] = mx.nd.zeros(shape=self.arg_shape_dict['res5c_branch2b_offset_bias'])
        arg_params['fc6_weight'] = mx.random.normal(0, 0.01, shape=self.arg_shape_dict['fc6_weight'])
        arg_params['fc6_bias'] = mx.nd.zeros(shape=self.arg_shape_dict['fc6_bias'])
        arg_params['score_weight'] = mx.random.normal(0, 0.01, shape=self.arg_shape_dict['score_weight'])
        arg_params['score_bias'] = mx.nd.zeros(shape=self.arg_shape_dict['score_bias'])
        arg_params['upsampling_weight'] = mx.nd.zeros(shape=self.arg_shape_dict['upsampling_weight'])

        init = mx.init.Initializer()
        init._init_bilinear('upsample_weight', arg_params['upsampling_weight'])

