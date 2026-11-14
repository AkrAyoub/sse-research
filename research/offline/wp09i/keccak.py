RC=[0x0000000000000001,0x0000000000008082,0x800000000000808a,0x8000000080008000,
0x000000000000808b,0x0000000080000001,0x8000000080008081,0x8000000000008009,
0x000000000000008a,0x0000000000000088,0x0000000080008009,0x000000008000000a,
0x000000008000808b,0x800000000000008b,0x8000000000008089,0x8000000000008003,
0x8000000000008002,0x8000000000000080,0x000000000000800a,0x800000008000000a,
0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
R=[[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
MASK=(1<<64)-1
def rot(v,k):return ((v<<k)|(v>>(64-k)))&MASK if k else v
def perm(a):
 for rc in RC:
  c=[a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
  d=[c[(x-1)%5]^rot(c[(x+1)%5],1) for x in range(5)]
  for x in range(5):
   for y in range(5):a[x+5*y]^=d[x]
  b=[0]*25
  for x in range(5):
   for y in range(5):b[y+5*((2*x+3*y)%5)]=rot(a[x+5*y],R[x][y])
  for x in range(5):
   for y in range(5):a[x+5*y]=b[x+5*y]^((~b[(x+1)%5+5*y])&b[(x+2)%5+5*y])
  a[0]^=rc
 return a
def keccak256(data):
 rate=136; pad=bytearray(data);pad.append(1)
 while len(pad)%rate!=rate-1:pad.append(0)
 pad.append(0x80)
 state=[0]*25
 for p in range(0,len(pad),rate):
  for k in range(rate//8):state[k]^=int.from_bytes(pad[p+8*k:p+8*k+8],'little')
  perm(state)
 return b''.join(x.to_bytes(8,'little') for x in state)[:32]
assert keccak256(b'').hex()=='c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',keccak256(b'').hex()
if __name__=='__main__':print('keccak empty',keccak256(b'').hex())
