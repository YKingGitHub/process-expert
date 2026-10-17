"""Explicit right-handed camera/rigid-transform contract, without CAD imports.

These are dataset conventions, not a claim about an engineering projection
standard. Source camera annotations are agent-authored and separately reviewed.
"""
import math

CANONICAL_CAMERAS = {
    'front': {'right': [1,0,0], 'up': [0,1,0]},
    'top': {'right': [1,0,0], 'up': [0,0,-1]},
    'right_side': {'right': [0,0,-1], 'up': [0,1,0]},
    'left_side': {'right': [0,0,1], 'up': [0,1,0]},
    'back': {'right': [-1,0,0], 'up': [0,1,0]},
    'bottom': {'right': [1,0,0], 'up': [0,0,1]},
}

def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def mv(m,v): return [dot(row,v) for row in m]
def transpose(m): return [list(col) for col in zip(*m)]
def determinant(m): return dot(m[0],cross(m[1],m[2]))

def basis(right,up):
    if any(not math.isfinite(x) for v in (right,up) for x in v):
        raise ValueError('Nonfinite camera basis')
    if len(right)!=3 or len(up)!=3 or abs(dot(right,right)-1)>1e-7 or abs(dot(up,up)-1)>1e-7 or abs(dot(right,up))>1e-7:
        raise ValueError('Camera right/up must be orthonormal')
    result=[list(right),list(up),cross(right,up)]
    if abs(determinant(result)-1)>1e-7: raise ValueError('Reflection is forbidden')
    return result

def rigid_transform(rotation,center):
    basis(rotation[0],rotation[1])
    if abs(determinant(rotation)-1)>1e-7: raise ValueError('Rotation must have determinant +1')
    t=[-x for x in mv(rotation,center)]
    forward=[row+[offset] for row,offset in zip(rotation,t)]+[[0,0,0,1]]
    inverse=[row+[c] for row,c in zip(transpose(rotation),center)]+[[0,0,0,1]]
    return forward,inverse

def point(transform,p): return mv(transform[:3],list(p)+[1])

def axis_angle(rotation):
    angle=math.acos(max(-1,min(1,(sum(rotation[i][i] for i in range(3))-1)/2)))
    if angle<1e-10: return [1,0,0],0.0
    if abs(angle-math.pi)<1e-8:
        i=max(range(3),key=lambda k:rotation[k][k]); axis=[0.0]*3
        axis[i]=math.sqrt(max(0,(rotation[i][i]+1)/2))
        for j in range(3):
            if j!=i: axis[j]=(rotation[i][j]+rotation[j][i])/(4*axis[i])
    else:
        axis=[(rotation[2][1]-rotation[1][2])/(2*math.sin(angle)),
              (rotation[0][2]-rotation[2][0])/(2*math.sin(angle)),
              (rotation[1][0]-rotation[0][1])/(2*math.sin(angle))]
    return axis,math.degrees(angle)

def camera_payload(right,up):
    rows=basis(right,up)
    return {'screen_right':rows[0], 'screen_up':rows[1], 'camera_from_direction':rows[2],
            'view_direction':[-x for x in rows[2]], 'projection':'orthographic'}

def pixel_matrix(right,up,pixels_per_mm,size=1024):
    """Canonical xyz in mm -> homogeneous image pixels (image y points down)."""
    return [[pixels_per_mm*x for x in right]+[size/2],
            [-pixels_per_mm*x for x in up]+[size/2], [0,0,0,1]]
