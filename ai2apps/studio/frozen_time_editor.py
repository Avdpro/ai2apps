"""Untrusted sampled-plan validation and generic filter execution.

The Package owns keyframes, interpolation and playback. Legacy frame_order is
retained solely for converting previously saved schema-1 results.
"""
import json
import math
from .frozen_time import CameraKey, FRAME_COUNTS

RANGES = {'pitch':(-20,20), 'yaw':(-20,20), 'roll':(-20,20), 'radius':(.6,1.4),
          'blur':(0,12), 'saturation':(0,2), 'exposure':(-2,2), 'brightness':(0,2)}
ORIGIN = CameraKey(0)


def parse_frame_plan(value):
    """Validate a Package-computed plan; never interpolate or interpret presets."""
    if not isinstance(value,str) or not value or len(value)>128000:
        raise ValueError('A bounded camera frame plan is required')
    data=json.loads(value)
    if not isinstance(data,dict) or set(data)!={'schema','frames','playback','poster'} or data['schema']!='ai2apps.camera-frames/v1':
        raise ValueError('Invalid camera frame plan schema')
    frames=data['frames']
    if not isinstance(frames,list) or len(frames) not in FRAME_COUNTS:
        raise ValueError('Unsupported Meridian frame count')
    for key in frames:
        if not isinstance(key,dict) or set(key)!=set(RANGES):
            raise ValueError('Invalid camera frame')
        for field,(lo,hi) in RANGES.items():
            x=key[field]
            if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:
                raise ValueError('Camera/filter value out of range: '+field)
    order=data['playback']
    if not isinstance(order,list) or not len(frames)<=len(order)<=2*len(frames) or order[:len(frames)]!=list(range(len(frames))) or any(type(i) is not int or not 0<=i<len(frames) for i in order):
        raise ValueError('Invalid playback frame indices')
    if type(data['poster']) is not int or not 0<=data['poster']<len(frames):
        raise ValueError('Invalid poster frame index')
    return data


def is_origin(key):
    return all(abs(getattr(key,f)-getattr(ORIGIN,f))<1e-8 for f in RANGES)


def frame_order(plan,return_origin):
    if not return_origin:
        return tuple(range(len(plan)))
    origins=[i for i,k in enumerate(plan) if is_origin(k)]
    if not origins:
        raise ValueError('No origin frame in camera curve')
    return tuple(range(len(plan)))+tuple(range(len(plan)-2,origins[-1]-1,-1))


def apply_filters(rgb,key):
    from PIL import Image,ImageEnhance,ImageFilter
    import numpy as np
    image=Image.fromarray(rgb)
    if key.blur: image=image.filter(ImageFilter.GaussianBlur(key.blur))
    if key.saturation!=1: image=ImageEnhance.Color(image).enhance(key.saturation)
    gain=2**key.exposure*key.brightness
    if gain!=1: image=ImageEnhance.Brightness(image).enhance(gain)
    return np.asarray(image)
