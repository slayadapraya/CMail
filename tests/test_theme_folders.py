import tempfile,unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import Mock
from aster.core import Store,Graph,AppError
from aster.theme import select_theme,customize_color,PRESETS,save_custom_theme
from aster.google import Gmail
from aster.imap_google import GmailIMAP,encode_folder,decode_folder
class ThemeFolderTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name))
 def tearDown(self):self.temp.cleanup()
 def test_custom_palette_survives_multiple_presets_and_restart(self):
  customize_color(self.store,'background','#010203');customize_color(self.store,'accent','#fedcba');self.store.set('dark',False);save_custom_theme(self.store)
  select_theme(self.store,'Cyber Mint');select_theme(self.store,'Deep Space');self.assertEqual(self.store.get('color_accent'),PRESETS['Deep Space']['accent'])
  reopened=Store(Path(self.temp.name));select_theme(reopened,'Custom');self.assertEqual(reopened.get('color_background'),'#010203');self.assertEqual(reopened.get('color_accent'),'#fedcba');self.assertFalse(reopened.get('dark'))
 def test_customizing_preset_seeds_complete_palette(self):
  select_theme(self.store,'Violet Circuit');customize_color(self.store,'accent','#123456');select_theme(self.store,'Graphite');select_theme(self.store,'Custom');self.assertEqual(self.store.get('color_accent'),'#123456');self.assertEqual(self.store.get('color_background'),PRESETS['Violet Circuit']['background'])
 def test_initial_default_restores_inherited_colours(self):
  select_theme(self.store,'Cyber Mint');select_theme(self.store,'Custom');self.assertIsNone(self.store.get('color_accent'));self.assertTrue(self.store.get('dark'))
 def test_google_folder_creation(self):
  gmail=Gmail(None);gmail.api=Mock(return_value={'id':'Label_42','name':'Projects'});self.assertEqual(gmail.create_folder('Projects'),{'id':'Label_42','displayName':'Projects'});self.assertEqual(gmail.api.call_args.args,('POST','labels',{'name':'Projects','labelListVisibility':'labelShow','messageListVisibility':'show'}))
 def test_graph_folder_creation(self):
  graph=Graph.__new__(Graph);graph.request=Mock(return_value={'id':'folder','displayName':'Projects'});self.assertEqual(graph.create_folder('Projects')['id'],'folder');self.assertEqual(graph.request.call_args.args,('POST','/me/mailFolders',{'displayName':'Projects'}))
 def test_imap_unicode_create_and_failure(self):
  name='日本 & Projects';encoded=encode_folder(name);self.assertEqual(decode_folder(encoded),name);gmail=GmailIMAP(None);client=Mock();client.create.return_value=('OK',[])
  @contextmanager
  def connection():yield client
  gmail.connection=connection;self.assertEqual(gmail.create_folder(name),{'id':encoded,'displayName':name});client.create.assert_called_once();client.create.return_value=('NO',[])
  with self.assertRaises(AppError):gmail.create_folder('Bad')
