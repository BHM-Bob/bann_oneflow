'''
Author: BHM-Bob 2262029386@qq.com
Date: 2023-03-21 00:12:32
LastEditors: BHM-Bob 2262029386@qq.com
LastEditTime: 2023-05-21 16:37:46
Description: 
'''
import oneflow as flow
import oneflow.nn.functional as F
from oneflow.utils.data import Dataset
from oneflow.utils.data import DataLoader

try:
    from bann_flow.utils import GlobalSettings, Mprint
except:
    from utils import GlobalSettings, Mprint

def denarmalize_img(x, mean = [0.485, 0.456, 0.406], std = [0.229, 0.224, 0.225]):
    mean = flow.tensor(mean).unsqueeze(1).unsqueeze(1)
    std = flow.tensor(std).unsqueeze(1).unsqueeze(1)
    return x * std + mean

class RandomSeqGenerator(object):
    def __init__(self, seqs:flow.Tensor, lables:flow.Tensor, args:GlobalSettings,
                 multiLoads:int = 6, maskRatio:float = 0.3, device:str = 'cpu'):
        self.args = args
        self.seqs = seqs
        self.lables = lables
        self.device = device
        self.sumSeqs = len(seqs)
        self.multiLoads = multiLoads
        self.isMask = maskRatio > 0
        self.maskRatio = flow.tensor(maskRatio, device = device)
    def __call__(self, idx:int):
        idxs = flow.randint(0, self.sumSeqs, size = [self.multiLoads])
        idxs[0] = idx
        seqs, lables = self.seqs[idxs], self.lables[idxs]
        if self.isMask:
            mask = flow.rand(self.args.input['single_shape'], device=self.device).ge(self.maskRatio)
            seqs.mul_(mask)
        return seqs, lables        

class SubDataSet(Dataset):
    """
    继承Dataset，作为训练时\n
    接受DataSetRAM分配的数据
    """
    def __init__(self, args:GlobalSettings, x:list, y:list,
                 x_transformer:list = None, y_transformer:list = None):
        super(SubDataSet,self).__init__()
        self.args = args
        self.x = x
        self.y = y
        self.size = len(x)
        if x_transformer is None:
            x_transformer = lambda x : x
        if y_transformer is None:
            y_transformer = lambda y : y
        self.x_transformer, self.y_transformer = x_transformer, y_transformer
        
    def __getitem__(self, idx):
        return self.x_transformer(self.x[idx]), self.y_transformer(self.y[idx])
    def __len__(self):
        return self.size

class DataSetRAM():
    """
    将数据加载到RAM储存并按比例分配生成DataLoader\n
    可以传入各种transformer以满足加载不同数据的需求，亦可以继承该类，使用自定义代码加载self.x和self.labels\n
    Parameters
    ----------
    x: original x, suppose to be a list of paths and so on.
    x_transfor_origin: transfer original x_i to data x_i, and this class will gather them into a list
    x_transfor_gather: transfer gathered x to data x
    """
    def __init__(self, args:GlobalSettings, load_part:str = 'pre', device:str = 'cpu',
                 x = None, y = None, x_transfer_origin = None, y_transfer_origin = None,
                 x_transfer_gather = None, y_transfer_gather = None):
        super(DataSetRAM, self).__init__()
        self.args = args
        self.x = []
        self.y = []
        self.load_db_ratio = args.load_db_ratio
        self.batch_size =args.batch_size
        self.load_part = load_part
        self.device = device
        
        if x is not None and x_transfer_origin is not None:
            x = self._check_list(x)
            self.x = [x_transfer_origin(x_i) for x_i in x]
            if x_transfer_gather is not None:
                self.x = x_transfer_gather(self.x)
        if y is not None and y_transfer_origin is not None:
            y = self._check_list(y)
            self.y = [x_transfer_origin(y_i) for y_i in y]
            if y_transfer_gather is not None:
                self.y = x_transfer_gather(self.y)
            
        self.size = len(self.x)
    
    def _check_list(self, x):
        return [x] if not isinstance(x, list) else x

    def split(self, divide:list[float],
              x_transformer:list = None, y_transformer:list = None):
        """divide : [0, 0.7, 0.9, 1] => train_70% val_20% test_10%"""
        ret = []
        if len(self.y) == 0:
            self.y = [0] * self.size
        x_transformer = [None]*len(divide) if x_transformer is None else x_transformer
        y_transformer = [None]*len(divide) if y_transformer is None else y_transformer
        for idx in range(len(divide) - 1):
            index1 = int(divide[idx  ]*self.size)
            index2 = int(divide[idx+1]*self.size)
            ret.append(
                DataLoader(
                    SubDataSet(args = self.args,
                               x = self.x[index1 : index2],
                               y = self.y[index1 : index2],
                               x_transformer = x_transformer[idx],
                               y_transformer = y_transformer[idx])
                    ,batch_size = self.batch_size, shuffle = True, drop_last=True))
            self.args.mp.mprint(f'dataSet{idx:d} size:{index2-index1:d}')
        return ret