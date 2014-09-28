# -*- coding: utf-8 -*-
"""
Locomotion features

"""

import numpy as np

from .. import utils
from .. import config

from . import events
from . import feature_comparisons as fc
# To avoid conflicting with variables named 'velocity', we 
# import this as 'velocity_module':
from . import velocity as velocity_module 


class LocomotionVelocityElement(object):
    
    def __init__(self,name,speed,direction):
        self.name = name
        self.speed = speed
        self.direction = direction
        
    def __eq__(self, other):
        return fc.corr_value_high(self.speed,other.speed,
                                  'locomotion.velocity.' + self.name + '.speed') and \
               fc.corr_value_high(self.direction,other.direction,
                                  'locomotion.velocity.' + self.name + '.direction')
    def __repr__(self):
        return utils.print_object(self)         

    @classmethod
    def from_disk(cls, parent_ref, name):
        
        self = cls.__new__(cls)        
    
             #   velocity['head_tip'] = velocity.pop('headTip')
        #velocity['tail_tip'] = velocity.pop('tailTip')
        #head_tip        
        
        self.name = name
        self.speed = utils._extract_time_from_disk(parent_ref, 'speed')
        self.direction = utils._extract_time_from_disk(parent_ref, 'direction')
        
        return self

class LocomotionVelocity(object):
    
    """
    This is for the 'velocity' locomotion feature. The helper function,
    'compute_velocity' is used elsewhere  

    Compute the worm velocity (speed & direction) at the
    head-tip/head/midbody/tail/tail-tip


    THIS IS OUT OF DATE

    Parameters
    ----------
    nw : a NormalizedWorm instance

    ventral_mode: int
      The ventral side mode:
        0 = unknown
        1 = clockwise
        2 = anticlockwise

    
    
    Returns
    -------
    dict
    A two-tiered dictionary:
        1st Tier:
            headTip = the tip of the head (1/12 the worm at 0.25s)
            head    = the head (1/6 the worm at 0.5s)
            midbody = the midbody (2/6 the worm at 0.5s)
            tail    = the tail (1/6 the worm at 0.5s)
            tailTip = the tip of the tail (1/12 the worm at 0.25s)
                and 'speed' and 'direction' in the second tier.
        2nd Tier:
            speed =
            direction = 

    """
    
    # NOTE: head_tip and tail_tip overlap head and tail, respectively, and
    #       this set of partitions does not cover the neck and hips
    attribute_keys = ['head_tip', 'head', 'midbody', 'tail', 'tail_tip']
    
    def __init__(self,features_ref,ventral_mode=0):
        #TODO: Ventral mode needs to be handled differently
        nw = features_ref.nw

        all_options = features_ref.options
    
        locomotion_options = all_options.locomotion
    
        data_keys = list(self.attribute_keys) #Make a copy. Data keys will 
        #correspond to sections of the skeleton. Attribute keys correspond to 
        #attributes of this class.

        if(all_options.mimic_old_behaviour):
            data_keys[2] = 'old_midbody_velocity'


        avg_body_angle = velocity_module.get_partition_angles(nw, 
                                          partition_key='body',
                                          data_key='skeletons',
                                          head_to_tail=False)

        sample_time_values = {
            'head_tip': locomotion_options.velocity_tip_diff,
            'head':     locomotion_options.velocity_body_diff,
            'midbody':  locomotion_options.velocity_body_diff,
            'tail':     locomotion_options.velocity_body_diff,
            'tail_tip': locomotion_options.velocity_tip_diff
        }

        for attribute_key, data_key in zip(self.attribute_keys, data_keys):
            x, y = nw.get_partition(data_key, 'skeletons', True)

            speed, direction = velocity_module.compute_velocity(x, y,
                                            avg_body_angle,
                                            sample_time_values[attribute_key],
                                            ventral_mode)[0:2]
                                            
            setattr(self,attribute_key,LocomotionVelocityElement(attribute_key,speed,direction))                                

    def __eq__(self, other):
        is_same = True
        for attribute_key in self.attribute_keys:
            is_same = getattr(self,attribute_key) == getattr(other,attribute_key)
            if not is_same:
                break

        return is_same

    def __repr__(self):
        return utils.print_object(self)

    @classmethod
    def from_disk(cls, parent_ref):
        
        self = cls.__new__(cls)

        velocity_ref = parent_ref['velocity']

        for key in self.attribute_keys:
            
            #NOTE: We'll eventually need to check for old or new data ...
            if key is 'head_tip':
                old_key = 'headTip'
            elif key is 'tail_tip':
                old_key = 'tailTip'
            else:
                old_key = key
            local_ref = velocity_ref[old_key]
            setattr(self,key,
                    LocomotionVelocityElement.from_disk(local_ref,key))      
        return self
        
        """
        velocity_ref = m_var['velocity']
        for key in velocity_ref:
            value = velocity_ref[key]
            temp_speed = utils._extract_time_from_disk(value, 'speed')
            temp_direc = utils._extract_time_from_disk(value, 'direction')
            velocity[key] = {'speed': temp_speed, 'direction': temp_direc}

        # NOTE: This only valid for MRC

        velocity['head_tip'] = velocity.pop('headTip')
        velocity['tail_tip'] = velocity.pop('tailTip')

        self.velocity = velocity
        """

    
#TODO: Transition this to a class as well - like LocomotionVelocity
def get_motion_codes(midbody_speed, skeleton_lengths):
    """ 
    Calculate motion codes of the locomotion events

    A locomotion feature.

    See feature description at 
      /documentation/Yemini%20Supplemental%20Data/Locomotion.md

    Parameters
    ---------------------------------------
    midbody_speed: numpy array 1 x n_frames
      from locomotion.velocity.midbody.speed / config.FPS
    skeleton_lengths: numpy array 1 x n_frames

    Returns
    ---------------------------------------
    The locomotion events; a dict (called locally all_events_dict) 
    with event fields:
      forward  - (event) forward locomotion
      paused   - (event) no locomotion (the worm is paused)
      backward - (event) backward locomotion
      mode     = [1 x num_frames] the locomotion mode:
                 -1 = backward locomotion
                  0 = no locomotion (the worm is paused)
                  1 = forward locomotion

    Notes
    ---------------------------------------
    Formerly +seg_worm / +features / @locomotion / getWormMotionCodes.m

    """
    # Initialize the worm speed and video frames.
    num_frames = len(midbody_speed)

    # Compute the midbody's "instantaneous" distance travelled at each frame,
    # distance per second / (frames per second) = distance per frame
    distance_per_frame = abs(midbody_speed / config.FPS)

    #  Interpolate the missing lengths.
    skeleton_lengths = utils.interpolate_with_threshold(
                           skeleton_lengths,
                           config.MOTION_CODES_LONGEST_NAN_RUN_TO_INTERPOLATE)

    #===================================
    # SPACE CONSTRAINTS
    # Make the speed and distance thresholds a fixed proportion of the
    # worm's length at the given frame:
    worm_speed_threshold = skeleton_lengths * config.SPEED_THRESHOLD_PCT
    worm_distance_threshold = skeleton_lengths * config.DISTANCE_THRSHOLD_PCT
    worm_pause_threshold = skeleton_lengths * config.PAUSE_THRESHOLD_PCT

    # Minimum speed and distance required for movement to
    # be considered "forward"
    min_forward_speed = worm_speed_threshold
    min_forward_distance = worm_distance_threshold

    # Minimum speed and distance required for movement to
    # be considered "backward"
    max_backward_speed = -worm_speed_threshold
    min_backward_distance = worm_distance_threshold

    # Boundaries between which the movement would be considered "paused"
    min_paused_speed = -worm_pause_threshold
    max_paused_speed = worm_pause_threshold

    # Note that there is no maximum forward speed nor minimum backward speed.
    frame_values = {'forward': 1, 'backward': -1, 'paused': 0}
    min_speeds = {'forward': min_forward_speed,
                  'backward': None,
                  'paused': min_paused_speed}
    max_speeds = {'forward': None,
                  'backward': max_backward_speed,
                  'paused': max_paused_speed}
    min_distance = {'forward': min_forward_distance,
                    'backward': min_backward_distance,
                    'paused': None}

    #===================================
    # TIME CONSTRAINTS
    # The minimum number of frames an event had to be taking place for
    # to be considered a legitimate event
    min_frames_threshold = \
        config.FPS * config.EVENT_MIN_FRAMES_THRESHOLD
    # Maximum number of contiguous contradicting frames within the event
    # before the event is considered to be over.
    max_interframes_threshold = \
        config.FPS * config.EVENT_MAX_INTER_FRAMES_THRESHOLD

    # This is the dictionary this function will return.  Keys will be:
    # forward
    # backward
    # paused
    # mode
    all_events_dict = {}

    # Start with a blank numpy array, full of NaNs:
    all_events_dict['mode'] = np.empty(num_frames, dtype='float') * np.NaN

    for motion_type in frame_values:
        # We will use EventFinder to determine when the
        # event type "motion_type" occurred
        ef = events.EventFinder()

        # "Space and time" constraints
        ef.min_distance_threshold = min_distance[motion_type]
        ef.max_distance_threshold = None  # we are not constraining max dist
        ef.min_speed_threshold = min_speeds[motion_type]
        ef.max_speed_threshold = max_speeds[motion_type]

        # "Time" constraints
        ef.min_frames_threshold = min_frames_threshold
        ef.max_inter_frames_threshold = max_interframes_threshold

        event_list = ef.get_events(midbody_speed, distance_per_frame)

        # Start at 1, not 7 for forward
        # What happens from 1900 to 1907

        # Obtain only events entirely before the num_frames intervals
        event_mask = event_list.get_event_mask(num_frames)

        # Take the start and stop indices and convert them to the structure
        # used in the feature files
        m_event = events.EventListWithFeatures(event_list,
                                               distance_per_frame,
                                               compute_distance_during_event=True)

        # Record this motion_type to our all_events_dict!
        # Assign event type to relevant frames of all_events_dict['mode']
        all_events_dict['mode'][event_mask] = frame_values[motion_type]
        all_events_dict[motion_type] = m_event

    return all_events_dict