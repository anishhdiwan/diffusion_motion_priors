import numpy as np
import os
import yaml
import zarr
import torch

# normalize data
def get_data_stats(data):
    data = data.reshape(-1,data.shape[-1])
    stats = {
        'min': np.min(data, axis=0),
        'max': np.max(data, axis=0)
    }
    return stats

def normalize_data(data, stats):
    # nomalize to [0,1]
    ndata = (data - stats['min']) / (stats['max'] - stats['min'])
    # normalize to [-1, 1]
    ndata = ndata * 2 - 1
    return ndata

def unnormalize_data(ndata, stats):
    ndata = (ndata + 1) / 2
    data = ndata * (stats['max'] - stats['min']) + stats['min']
    return data

def pair_data(data_dict, episode_ends, num_amp_obs_steps, num_amp_obs_per_step, device):
    """
    Create sets of data [ [s1,s2,.. sn], [s2,s3,.. s+1] ...]
    n = num_amp_obs_steps
    """
    for key, data in data_dict.items():
        # paired_size = data.shape[0] - len(episode_ends)*(num_amp_obs_steps - 1)
        # paired_data = torch.zeros((paired_size, num_amp_obs_steps*num_amp_obs_per_step), device=device, dtype=torch.float)

        episode_ends = episode_ends.tolist()
        if data.shape[0] in episode_ends:
            episode_ends.remove(data.shape[0])
            episode_ends.append(data.shape[0]-1)

        del_list = []
        for end in episode_ends:
            for i in range(num_amp_obs_steps - 1):
                if i != 0:
                    del_list.append((end - i))
        del_list = del_list + episode_ends

        shifted_copies = []
        for i in range(num_amp_obs_steps - 1):
            shifted_array = np.copy(data)
            shifted_array[:-1-i,:] = shifted_array[1+i:,:]
            # shifted_array[-1-i:,:] = 0.0
            # shifted_array = np.delete(shifted_array, [-1-i:])
            shifted_copies.append(shifted_array)


        data = np.delete(data, del_list, axis=0)
        for idx, arr in enumerate(shifted_copies):
            arr = np.delete(arr, del_list, axis=0)
            shifted_copies[idx] = arr

        shifted_copies.insert(0, data)
        paired_data = np.concatenate(shifted_copies, axis=1)

        return paired_data




class MotionLib():
    def __init__(self, motion_file, num_amp_obs_steps, num_amp_obs_per_step, device=None):
        if device == None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device
        
        self.num_amp_obs_steps = num_amp_obs_steps
        self.num_amp_obs_per_step = num_amp_obs_per_step
        self._load_motions(motion_file)
        

    def _load_motions(self, motion_file):
        dataset_root = zarr.open(motion_file, 'r')
        # All demonstration episodes are concatinated in the first dimension N
        train_data = {
            # (N, action_dim)
            # 'action': dataset_root['data']['action'][:],
            # (N, obs_dim)
            'obs': dataset_root['data']['state'][:]
        }
        # Marks one-past the last index for each episode
        episode_ends = dataset_root['meta']['episode_ends'][:]

        # compute statistics and normalized data to [-1,1]
        stats = dict()
        normalized_train_data = dict()
        for key, data in train_data.items():
            stats[key] = get_data_stats(data)
            normalized_train_data[key] = normalize_data(data, stats[key])
        paired_normalized_data = pair_data(normalized_train_data, episode_ends, self.num_amp_obs_steps, self.num_amp_obs_per_step, self.device)

        self.stats = stats
        self.normalized_train_data = normalized_train_data
        self.paired_normalized_data = paired_normalized_data

    def sample_motions(num_samples):
        # TODO: sample considering episode ends
        pass