"""Security scanner contract for imports and fetch hooks."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.security import ScanResult, scan_import, scan_payload


class ScanImportTests(unittest.TestCase):
    def test_blocks_empty_location(self):
        result = scan_import("   ")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "blocked_empty")

    def test_allows_remote_url(self):
        with self.assertLogs("warframe_lore.v1.security", level="INFO"):
            result = scan_import("https://example.org/wiki")
        self.assertTrue(result.allowed)
        self.assertEqual(result.code, "allowed_remote")
        self.assertIn("téléchargement", result.reason)

    def test_blocks_scripts_and_exec_vectors(self):
        for name in (
            "tool.exe", "run.ps1", "run.bat", "app.js", "x.sh",
            "x.dll", "x.lnk", "x.reg", "x.hta", "x.msi",
        ):
            with self.subTest(name=name):
                result = scan_import(f"C:/tmp/{name}")
                self.assertFalse(result.allowed)
                self.assertIn(result.code, {"blocked_script", "blocked_active_content"})

    def test_blocks_macro_documents(self):
        for name in ("doc.docm", "sheet.xlsm", "slides.pptm", "tpl.dotm"):
            with self.subTest(name=name):
                result = scan_import(name)
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "blocked_macro")

    def test_blocks_active_content(self):
        for name in ("page.html", "icon.svg", "file.pdf", "data.xml"):
            with self.subTest(name=name):
                result = scan_import(name)
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "blocked_active_content")

    def test_blocks_archives(self):
        for name in ("data.zip", "data.7z", "data.rar", "data.tar.gz"):
            with self.subTest(name=name):
                result = scan_import(name)
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "blocked_archive")

    def test_blocks_images_without_qr_detector(self):
        with self.assertLogs("warframe_lore.v1.security", level="WARNING"):
            result = scan_import("photo.png")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "blocked_qr_unverified")

    def test_allows_image_when_no_qr_detected(self):
        result = scan_import("photo.jpg", qr_detector=lambda _p: False)
        self.assertTrue(result.allowed)
        self.assertEqual(result.code, "allowed_image")

    def test_blocks_image_when_qr_detected(self):
        with self.assertLogs("warframe_lore.v1.security", level="WARNING"):
            result = scan_import("photo.webp", qr_detector=lambda _p: True)
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "blocked_qr_detected")

    def test_allows_safe_local_documents(self):
        for name in ("notes.txt", "notes.md", "data.json", "data.csv"):
            with self.subTest(name=name):
                result = scan_import(name)
                self.assertTrue(result.allowed)
                self.assertEqual(result.code, "allowed_local")

    def test_payload_hook_uses_location_policy(self):
        blocked = scan_payload("archive.zip", content=b"PK")
        allowed = scan_payload("https://example.org/doc")
        self.assertIsInstance(blocked, ScanResult)
        self.assertFalse(blocked.allowed)
        self.assertTrue(allowed.allowed)


class UiCompatibilityTests(unittest.TestCase):
    def test_validate_import_delegates_to_scanner(self):
        from warframe_lore.v1.scraper.UI.security import validate_import

        ok, reason = validate_import("https://example.org")
        self.assertTrue(ok)
        self.assertIsInstance(reason, str)
        blocked, reason = validate_import("malware.exe")
        self.assertFalse(blocked)
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
