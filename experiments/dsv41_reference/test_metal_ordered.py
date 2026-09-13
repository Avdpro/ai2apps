import json,unittest
from pathlib import Path
import torch
import cpu_kernel
import metal_dense
import metal_dense_ordered
from test_metal_dense import DenseTests

class OrderedTests(DenseTests):
    def setUp(self):
        self.old_dtype=torch.get_default_dtype()
        super().setUp()
        self.old_kernel=metal_dense.kernel
        metal_dense.kernel=metal_dense_ordered.kernel
    def tearDown(self):
        metal_dense.kernel=self.old_kernel
        torch.set_default_dtype(self.old_dtype)
    def test_real_rounding_boundaries(self):
        for path in Path(__file__).with_name('fixtures').glob(getattr(self,'fixture_pattern','fp8-rounding-case*.json')):
            data=json.loads(path.read_text())
            def value(name,dtype):return torch.tensor(data[name],dtype=torch.uint8).view(dtype)[None,:]
            a=value('a',torch.float8_e4m3fn);b=value('b',torch.float8_e4m3fn)
            sa=value('sa',torch.float8_e8m0fnu);sb=value('sb',torch.float8_e8m0fnu)
            # CPU GEMM reduction can depend on M/N. Preserve the real shape;
            # unrelated rows may be zero but must not collapse this to a dot.
            m,n,row,col=(data[k] for k in ('input_rows','output_rows','row','column'))
            full_a=torch.zeros(m,a.shape[1]).to(a.dtype)
            full_b=torch.zeros(n,b.shape[1]).to(b.dtype)
            full_sa=torch.ones(m,sa.shape[1]).to(sa.dtype)
            full_sb=torch.ones((n+31)//32,sb.shape[1]).to(sb.dtype)
            full_a[row]=a[0];full_b[col]=b[0]
            full_sa[row]=sa[0];full_sb[col//32]=sb[0]
            a,b,sa,sb=full_a,full_b,full_sa,full_sb
            expected=cpu_kernel.fp8_gemm(a,sa,b,sb,block_size=32)
            actual=metal_dense.fp8_gemm(a,sa,b,sb,block_size=32)
            self.assertEqual(expected[row,col].item(),data['expected'],str(path))
            self.assertTrue(torch.equal(actual.view(torch.uint8),expected.view(torch.uint8)),str(path))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(OrderedTests)
    result=unittest.TextTestRunner().run(suite)
    raise SystemExit(not result.wasSuccessful())
