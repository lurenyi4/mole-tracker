"""Display transforms only; persisted coordinates always refer to the original raster."""


def display_point(point, size, rotation):
    x,y=point;w,h=size
    return ([x,y],[h-1-y,x],[w-1-x,h-1-y],[y,w-1-x])[rotation%4]


def original_point(point, size, rotation):
    x,y=point;w,h=size
    return ([x,y],[y,h-1-x],[w-1-x,h-1-y],[w-1-y,x])[rotation%4]
