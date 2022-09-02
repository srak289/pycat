def attr_name(s):
    return s.lower().strip().replace('/','_').replace('-','_')

__all__ = ['attr_name']
