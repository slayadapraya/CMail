import unittest,json
from aster import dockmodel as d
class DockTests(unittest.TestCase):
 def test_split_float_return(self):
  v=d.default();main=v['tree']['id'];self.assertTrue(d.move(v,'calendar',main,'right'));self.assertEqual(v['tree']['kind'],'split');self.assertEqual(d.location(v,'calendar')['tabs'],['calendar'])
  d.move(v,'calendar');self.assertEqual(len(v['floating']),1);self.assertEqual(v['tree']['kind'],'group')
  d.move(v,'calendar',v['tree']['id']);self.assertFalse(v['floating']);self.assertEqual(len(v['tree']['tabs']),4)
 def test_reorder_and_no_empty_split(self):
  v=d.default();d.move(v,'drafts',v['tree']['id'],'center',0);self.assertEqual(v['tree']['tabs'][0],'drafts');d.move(v,'calendar',v['tree']['id'],'bottom');leaf=d.location(v,'calendar');self.assertFalse(d.move(v,'calendar',leaf['id'],'left'))
 def test_normalize_duplicate_corrupt(self):
  v=d.normalize(dict(tree=dict(kind='group',tabs=['mail','mail','bogus']),floating=[dict(group=dict(kind='group',tabs=['calendar','mail']),width='bad')],active='bogus'))
  self.assertEqual(sorted(p for g in d.groups(v) for p in g['tabs']),sorted(d.PANELS));self.assertEqual(v['active'],'mail');self.assertEqual(v['floating'][0]['width'],900)
 def test_roundtrip(self):
  v=d.default();d.move(v,'calendar',v['tree']['id'],'right');d.move(v,'contacts');self.assertEqual(d.normalize(json.loads(json.dumps(v))),v)
if __name__=='__main__':unittest.main()
