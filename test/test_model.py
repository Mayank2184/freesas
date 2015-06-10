#!/usr/bin/python
__author__ = "Guillaume"
__license__ = "MIT"
__copyright__ = "2015, ESRF"

import numpy
import unittest
import os
import tempfile
from test.utilstests import base, join
from freesas.model import SASModel
from freesas.transformations import translation_from_matrix, euler_from_matrix

def assign_random_mol(inf=None, sup=None):
    if not inf: inf = 0
    if not sup: sup = 100
    molecule = numpy.random.randint(inf ,sup, size=400).reshape(100,4).astype(float)
    molecule[:,-1] = 1.0
    m = SASModel(molecule)
    return m

class TesttParser(unittest.TestCase):
    testfile = join(base, "testdata", "model-01.pdb")

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tmpdir = tempfile.mkdtemp()
        self.outfile = join(self.tmpdir, "out.pdb")

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        for fn in (self.outfile,self.tmpdir):
            if os.path.exists(fn):
                if os.path.isdir(fn):
                    os.rmdir(fn)
                else:
                    os.unlink(fn)

    def test_same(self):
        m = SASModel()
        m.read(self.testfile)
        m.save(self.outfile)
        infile = open(self.testfile).read()
        outfile = open(self.outfile).read()
        self.assertEqual(infile, outfile, msg="file content is the same")

    def test_centroid(self):
        m = assign_random_mol()
        m.centroid()
        assert len(m.com)==3, "center of mass has not been saved correctly : length of COM position vector = %s!=3"%(len(m.com))
        mol_centered = m.atoms[:,0:3]-m.com
        center = mol_centered.mean(axis=0)
        norm = (center*center).sum()
        self.assertAlmostEqual(norm, 0, 12, msg="molecule is not centered : norm of the COM position vector %s!=0"%(norm))

    def test_inertia_tensor(self):
        m = assign_random_mol()
        m.inertiatensor()
        tensor = m.inertensor
        assert tensor.shape==(3,3), "inertia tensor has not been saved correctly : shape of inertia matrix = %s"%(tensor.shape)

    def test_canonical_translate(self):
        m = assign_random_mol()
        trans = m.canonical_translate()
        assert trans.shape==(4,4), "pb with translation matrix shape: shape=%s"%(trans.shape)
        com = m.com
        com_componants = [com[0], com[1], com[2]]
        trans_vect = [-trans[0,-1], -trans[1,-1], -trans[2,-1]]
        self.assertEqual(com_componants, trans_vect, msg="do not translate on canonical position")

    def test_canonical_rotate(self):
        m = assign_random_mol()
        rot = m.canonical_rotate()
        assert rot.shape==(4,4), "pb with rotation matrix shape"
        assert m.enantiomer, "enantiomer has not been selected"
        det = numpy.linalg.det(rot)
        self.assertAlmostEqual(det, 1, 10, msg="rotation matrix determinant is not 1: %s"%(det))

    def test_canonical_parameters(self):
        m = assign_random_mol()
        m.canonical_parameters()
        can_param = m.can_param
        assert len(can_param)==6, "canonical parameters has not been saved properly"
        com_trans = translation_from_matrix(m.canonical_translate())
        euler_rot = euler_from_matrix(m.canonical_rotate())
        out_param = [com_trans[0], com_trans[1], com_trans[2], euler_rot[0], euler_rot[1], euler_rot[2]]
        self.assertEqual(can_param, out_param, msg="canonical parameters are not the good ones")

    def test_dist(self):
        m = assign_random_mol()
        n = SASModel(m.atoms)
        distance = m.dist(n, m.atoms, n.atoms)
        self.assertEqual(distance, 0, msg="NSD different of 0: %s!=0"%(distance))

    def test_can_transform(self):
        m = assign_random_mol()
        m.canonical_parameters()
        p0 = m.can_param
        mol1 = m.transform(p0,[1,1,1])
        assert abs(mol1-m.atoms).max() != 0 ,"molecule did not move"
        m.atoms = mol1
        m.centroid()
        m.inertiatensor()
        com = m.com
        tensor = m.inertensor
        diag = numpy.eye(3)
        matrix = tensor-tensor*diag
        self.assertAlmostEqual(abs(com).sum(), 0, 10, msg="molecule not on its center of mass")
        self.assertAlmostEqual(abs(matrix).sum(), 0, 10, "inertia moments unaligned ")

    def test_dist_move(self):
        m = assign_random_mol()
        n = SASModel(m.atoms)
        m.canonical_parameters()
        n.canonical_parameters()
        assert abs(n.atoms-m.atoms).max()==0, "molecules are different"
        p0 = m.can_param
        dist_after_mvt = m.dist_after_movement(p0, n, [1,1,1])
        self.assertEqual(dist_after_mvt, 0, msg="NSD different of 0: %s!=0"%(dist_after_mvt))
        
def test_suite_all_model():
    testSuite = unittest.TestSuite()
    testSuite.addTest(TesttParser("test_same"))
    testSuite.addTest(TesttParser("test_centroid"))
    testSuite.addTest(TesttParser("test_inertia_tensor"))
    testSuite.addTest(TesttParser("test_canonical_translate"))
    testSuite.addTest(TesttParser("test_canonical_rotate"))
    testSuite.addTest(TesttParser("test_canonical_parameters"))
    testSuite.addTest(TesttParser("test_dist"))
    testSuite.addTest(TesttParser("test_can_transform"))
    testSuite.addTest(TesttParser("test_dist_move"))
    return testSuite

if __name__ == '__main__':
    mysuite = test_suite_all_model()
    runner = unittest.TextTestRunner()
    runner.run(mysuite)