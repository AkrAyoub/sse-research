"""Milestone III submission structure regression tests."""
from pathlib import Path
import sys
import tempfile
import unittest
from reportlab.pdfgen import canvas
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from package_milestone3 import package

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'contracts').mkdir()
        for i in range(5):
            (self.root/'contracts'/f'Contract{i}.sol').write_text('pragma solidity ^0.8.24;\n',encoding='utf8')
        self.pdf=self.root/'article.pdf'
    def make_pdf(self, pages, content):
        c=canvas.Canvas(str(self.pdf))
        for _ in range(pages):
            c.drawString(50,700,content)
            c.showPage()
        c.save()
    def test_expected_submission_structure(self):
        import zipfile
        self.make_pdf(2,'AI Usage Disclaimer before References')
        package(self.root,self.pdf,self.root/'submission.zip')
        with zipfile.ZipFile(self.root/'submission.zip') as z:
            self.assertEqual(sorted(z.namelist()),['Article.pdf']+[f'contracts/Contract{i}.sol' for i in range(5)])
    def test_reject_over_six_pages(self):
        self.make_pdf(7,'AI Usage Disclaimer before References')
        with self.assertRaisesRegex(ValueError,'1–6 pages'):
            package(self.root,self.pdf,self.root/'submission.zip')
    def test_reject_missing_ai_disclosure(self):
        self.make_pdf(1,'Introduction References')
        with self.assertRaisesRegex(ValueError,'AI Usage Disclaimer'):
            package(self.root,self.pdf,self.root/'submission.zip')
if __name__=='__main__':unittest.main()
