__author__ = "Guillaume"
__license__ = "MIT"
__copyright__ = "2015, ESRF"

import numpy
import threading
try:
    from . import _distance
except ImportError:
    _distance = None

def delta_expand(vec1, vec2):
    """
    @param vec1, vec2: 1d-array
    @return: difference v1-v2 for any element of v1 and v2 (i.e a 2D array)
    """
    v1 = numpy.ascontiguousarray(vec1)
    v2 = numpy.ascontiguousarray(vec2)
    v1.shape = -1,1
    v2.shape = 1,-1
    v1.strides = v1.strides[0],0
    v2.strides = 0,v2.strides[-1]
    return v1-v2


class SASModel:
    def __init__(self):
        self.atoms = []
        self.radius = 1.0
        self.header = "" # header of the PDB file
        self.com = []
        self._fineness = None
        self.inertensor = []
        self._sem = threading.Semaphore()

    def __repr__(self):
        return "SAS model with %i atoms"%len(self.atoms)

    def read(self, filename):
        """
        read the PDB file
        extract coordinates of each dummy atom
        """
        header = []
        atoms = []
        for line in open(filename):
            if line.startswith("ATOM"):
                args = line.split()
                x = float(args[6])
                y = float(args[7])
                z = float(args[8])
                atoms.append([x, y, z])
            header.append(line)
        self.header = header
        self.atoms = numpy.array(atoms)

    def save(self, filename):
        """
        save the position of each dummy atom in a PDB file
        """
        nr = 0
        with open(filename, "w") as pdbout:
            for line in self.header:
                if line.startswith("ATOM"):
                    if nr<self.atoms.shape[0]:
                        line = line[:30]+"%8.3f%8.3f%8.3f"%tuple(self.atoms[nr])+line[54:]
                    else:
                        line = ""
                    nr += 1
                pdbout.write(line)

    def centroid(self):
        """
        return the center of mass of the protein
        """
        mol = self.atoms
        self.com = mol.mean(axis=0)

    def inertiatensor(self):
        """
        calculate the inertia tensor of the protein
        """
        mol = self.atoms - self.com
        self.inertensor = numpy.empty((3, 3), dtype = "float")
        delta_kron = lambda i, j : 1 if i==j else 0
        for i in range(3):
            for j in range(i,3):
                self.inertensor[i,j]= self.inertensor[j,i] = (delta_kron(i,j)*(mol**2).sum(axis=1) - (mol[:,i]*mol[:,j])).sum()/mol.shape[0]
    
    def canonical_translate(self):
        """
        Calculate the translation matrix to translate the center of mass of the molecule on the origine of the base
        """
        trans = numpy.identity(4, dtype = "float")
        trans[0:3,3] = -self.com
        return trans
                
    def canonical_rotate(self):
        """
        Calculate the rotation matrix to align inertia momentum of the molecule on principal axis.
        Return a matrix with a determinant = 1
        """
        w, v = numpy.linalg.eigh(self.inertensor)
        mat = v[:, w.argsort()]
        
        b = numpy.array([[0,0,0,1]])
        b.shape = 4,1
    
        return numpy.append(numpy.append(mat.T,numpy.zeros((1,3)), axis=0), b, axis=1)
    
    def canonical_position(self):
        """
        Calculate coordinates of each dummy atoms with the molecule in its canonical position
        The molecule is put on its canonical position
        """
        mol = self.atoms
        mol = numpy.append(mol.T, numpy.ones((1,mol.shape[0])), axis=0)
        
        mol = numpy.dot(self.canonical_translate(), mol)
        mol = numpy.dot(self.canonical_rotate(), mol)
        molfinal = numpy.delete(mol, 3, axis=0)
        
        self.atoms = molfinal.T
        
    
    def _calc_fineness(self, use_cython=True):
        """
        Calculate the fineness of the structure, i.e the average distance between the neighboring points in the model
        """
        if _distance and use_cython:
            return _distance.calc_fineness(self.atoms)

        else:
            D = delta_expand(self.atoms[:,0], self.atoms[:,0])**2+delta_expand(self.atoms[:,1], self.atoms[:,1])**2+delta_expand(self.atoms[:,2], self.atoms[:,2])**2
            d12 = (D.max()*numpy.eye(self.atoms[:,0].size)+D).min(axis=0).mean()
            fineness = numpy.sqrt(d12)
            return fineness

    @property
    def fineness(self):
        if self._fineness is None:
            with self._sem:
                if self._fineness is None:
                    self._fineness = self._calc_fineness()
        return self._fineness

    def dist(self, other, use_cython=True):
        """
        Calculate the distance with another model
        """
        if _distance and use_cython:
            return _distance.calc_distance(self.atoms, other.atoms, self.fineness, other.fineness)
        
        else:
            mol1 = self.atoms
            mol2 = other.atoms

            mol1x = mol1[:,0]
            mol1y = mol1[:,1]
            mol1z = mol1[:,2]
            mol1x.shape = mol1.shape[0],1
            mol1y.shape = mol1.shape[0],1
            mol1z.shape = mol1.shape[0],1

            mol2x = mol2[:,0]
            mol2y = mol2[:,1]
            mol2z = mol2[:,2]
            mol2x.shape = mol2.shape[0],1
            mol2y.shape = mol2.shape[0],1
            mol2z.shape = mol2.shape[0],1

            d2=delta_expand(mol1x,mol2x)**2+delta_expand(mol1y,mol2y)**2+delta_expand(mol1z,mol2z)**2

            D = (0.5*((1./((mol1.shape[0])*other.fineness*other.fineness))*(d2.min(axis=1).sum())+(1./((mol2.shape[0])*self.fineness*self.fineness))*(d2.min(axis=0)).sum()))**0.5
            return D