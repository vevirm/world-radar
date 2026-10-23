import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import eu_observatory as o
class Checks(unittest.TestCase):
 def test_bad_topic(self):
  c={'original_claim':'European sustainable aviation fuel adoption will increase across airlines by 2030','title':'Aviation scenarios','year':2015}
  p={'title':'Cereal supply change in Pakistan','abstract':'Wheat and rice yields under price constraints','year':2024}
  self.assertIsNone(o.compare(c,p))
 def test_same_subject(self):
  c={'original_claim':'European sustainable aviation fuel adoption will increase across airlines by 2030','title':'Aviation scenarios','year':2015}
  p={'title':'Sustainable aviation fuel adoption in European airlines','abstract':'Deployment of aviation jet fuel in Europe rose amid policy incentives','year':2024}
  self.assertIsNotNone(o.compare(c,p))
 def test_earlier(self):
  c={'original_claim':'Flood damage and population exposure in Europe increases through 2050','title':'EU flood scenario','year':2015}
  p={'title':'Flood damage and population exposure in Europe','abstract':'Flood damage and exposure','year':2012}
  self.assertIsNone(o.compare(c,p))
 def test_queries(self):
  c={'original_claim':'Flood damage and population exposure in Europe increases through 2050','title':'EU flood scenario','year':2015}
  self.assertIn('flood', ' '.join(o.queries(c)))
if __name__=='__main__':unittest.main()
