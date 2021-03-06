# @Time   : 2020/9/16
# @Author : Yushuo Chen
# @Email  : chenyushuo@ruc.edu.cn

# UPDATE:
# @Time   : 2020/9/16
# @Author : Yushuo Chen
# @Email  : chenyushuo@ruc.edu.cn

"""
recbole.data.sequential_dataset
###############################
"""

import copy

import numpy as np

from recbole.data.dataset import Dataset


class SequentialDataset(Dataset):
    """:class:`SequentialDataset` is based on :class:`~recbole.data.dataset.dataset.Dataset`,
    and provides augmentation interface to adapt to Sequential Recommendation,
    which can accelerate the data loader.

    Attributes:
        uid_list (numpy.ndarray): List of user id after augmentation.

        item_list_index (numpy.ndarray): List of indexes of item sequence after augmentation.

        target_index (numpy.ndarray): List of indexes of target item id after augmentation.

        item_list_length (numpy.ndarray): List of item sequences' length after augmentation.

    """

    def __init__(self, config, saved_dataset=None):
        super().__init__(config, saved_dataset=saved_dataset)

    def prepare_data_augmentation(self):
        """Augmentation processing for sequential dataset.

        E.g., ``u1`` has purchase sequence ``<i1, i2, i3, i4>``,
        then after augmentation, we will generate three cases.

        ``u1, <i1> | i2``

        (Which means given user_id ``u1`` and item_seq ``<i1>``,
        we need to predict the next item ``i2``.)

        The other cases are below:

        ``u1, <i1, i2> | i3``

        ``u1, <i1, i2, i3> | i4``

        Note:
            Actually, we do not really generate these new item sequences.
            One user's item sequence is stored only once in memory.
            We store the index (slice) of each item sequence after augmentation,
            which saves memory and accelerates a lot.
        """
        self.logger.debug('prepare_data_augmentation')

        self._check_field('uid_field', 'time_field')
        max_item_list_len = self.config['MAX_ITEM_LIST_LENGTH']
        self.sort(by=[self.uid_field, self.time_field], ascending=True)
        last_uid = None
        uid_list, item_list_index, target_index, item_list_length = [], [], [], []
        seq_start = 0
        for i, uid in enumerate(self.inter_feat[self.uid_field].numpy()):
            if last_uid != uid:
                last_uid = uid
                seq_start = i
            else:
                if i - seq_start > max_item_list_len:
                    seq_start += 1
                uid_list.append(uid)
                item_list_index.append(slice(seq_start, i))
                target_index.append(i)
                item_list_length.append(i - seq_start)

        self.uid_list = np.array(uid_list)
        self.item_list_index = np.array(item_list_index)
        self.target_index = np.array(target_index)
        self.item_list_length = np.array(item_list_length)

    def leave_one_out(self, group_by, leave_one_num=1):
        self.logger.debug(f'Leave one out, group_by=[{group_by}], leave_one_num=[{leave_one_num}].')
        if group_by is None:
            raise ValueError('Leave one out strategy require a group field.')
        if group_by != self.uid_field:
            raise ValueError('Sequential models require group by user.')

        self.prepare_data_augmentation()
        grouped_index = self._grouped_index(self.uid_list)
        next_index = self._split_index_by_leave_one_out(grouped_index, leave_one_num)

        self._drop_unused_col()
        next_ds = []
        for index in next_index:
            ds = copy.copy(self)
            for field in ['uid_list', 'item_list_index', 'target_index', 'item_list_length']:
                setattr(ds, field, np.array(getattr(ds, field)[index]))
            next_ds.append(ds)
        return next_ds

    def build(self, eval_setting):
        ordering_args = eval_setting.ordering_args
        if ordering_args['strategy'] == 'shuffle':
            raise ValueError('Ordering strategy `shuffle` is not supported in sequential models.')
        elif ordering_args['strategy'] == 'by':
            if ordering_args['field'] != self.time_field:
                raise ValueError('Sequential models require `TO` (time ordering) strategy.')
            if ordering_args['ascending'] is not True:
                raise ValueError('Sequential models require `time_field` to sort in ascending order.')

        group_field = eval_setting.group_field

        split_args = eval_setting.split_args
        if split_args['strategy'] == 'loo':
            return self.leave_one_out(group_by=group_field, leave_one_num=split_args['leave_one_num'])
        else:
            ValueError('Sequential models require `loo` (leave one out) split strategy.')
