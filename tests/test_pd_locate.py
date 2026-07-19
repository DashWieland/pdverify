"""Tests for Pd version parsing helpers. No Pd required."""

from pdverify.pd_locate import _version_from_path


def test_version_from_macos_app_path():
    p = "/Applications/Pd-0.56-2.app/Contents/Resources/bin/pd"
    assert _version_from_path(p) == "0.56.2"


def test_version_from_bundled_path():
    p = r"C:\proj\tools\pd-0.54-1\bin\pd.com"
    assert _version_from_path(p) == "0.54.1"


def test_version_from_plain_path_is_empty():
    assert _version_from_path("/usr/bin/pd") == ""
