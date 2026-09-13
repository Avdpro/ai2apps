import unittest
import metal_dense
import metal_dense_cpu_order
from test_metal_ordered import OrderedTests

class CPUOrderTests(OrderedTests):
    fixture_pattern='*rounding-case*.json'
    def setUp(self):
        super().setUp()
        self.old_gemm=metal_dense.fp8_gemm
        metal_dense.fp8_gemm=metal_dense_cpu_order.fp8_gemm
    def tearDown(self):
        metal_dense.fp8_gemm=self.old_gemm
        super().tearDown()

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(CPUOrderTests))
    raise SystemExit(not result.wasSuccessful())
