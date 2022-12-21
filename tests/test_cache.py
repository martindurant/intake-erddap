#!/usr/bin/env pytest
"""Unit tests for caching support."""
import gzip
import os
import shutil
import tempfile
import time

from pathlib import Path
from unittest import mock

import pytest

from intake_erddap import cache


@pytest.fixture
def tempdir():
    tempdir = tempfile.mkdtemp()
    yield tempdir
    if os.path.exists(tempdir):
        shutil.rmtree(tempdir)


@mock.patch("appdirs.user_cache_dir")
def test_cache_file(user_cache_dir_mock, tempdir):
    user_cache_dir_mock.return_value = tempdir
    url = "http://kevinbacon.invalid/erddap/advanced?blahbah"
    store = cache.CacheStore()
    filepath = store.cache_file(url)
    assert filepath.parent == Path(tempdir)
    sha = cache.CacheStore.hash_url(url)
    assert filepath.name == f"{sha}.gz"


@mock.patch("requests.get")
@mock.patch("appdirs.user_cache_dir")
def test_cache_csv(user_cache_dir_mock, http_get_mock, tempdir):
    user_cache_dir_mock.return_value = tempdir
    resp = mock.Mock()
    resp.content = b"blahblah"
    http_get_mock.return_value = resp
    url = "http://kevinbacon.invalid/erddap/advanced?blahbah"
    store = cache.CacheStore()
    store.cache_response(url)
    sha = store.hash_url(url)
    target = Path(tempdir) / f"{sha}.gz"
    assert target.exists()
    assert http_get_mock.called_with(url)
    with gzip.open(target, "rt", encoding="utf-8") as f:
        buf = f.read()
        assert buf == "blahblah"


@mock.patch("requests.get")
@mock.patch("appdirs.user_cache_dir")
def test_clearing_cache(user_cache_dir_mock, http_get_mock, tempdir):
    user_cache_dir_mock.return_value = tempdir
    resp = mock.Mock()
    resp.content = b"blahblah"
    http_get_mock.return_value = resp
    url = "http://kevinbacon.invalid/erddap/advanced?blahbah"
    store = cache.CacheStore()
    store.cache_response(url)
    sha = store.hash_url(url)
    target = Path(tempdir) / f"{sha}.gz"

    store.clear_cache()
    assert not target.exists()
    store.cache_response(url)
    assert target.exists()

    # Clear cached files older than 100 s. The file we just created is brand new so should remain.
    store.clear_cache(100)
    assert target.exists()

    # Now change the mtime of the file to be 500 s old
    now = time.time()
    os.utime(target, (now - 500, now - 500))
    store.clear_cache(100)
    assert not target.exists()


@mock.patch("appdirs.user_cache_dir")
def test_cache_no_dir(user_cache_dir_mock, tempdir):
    """Tests that the cache store will create the cache dir if it doesn't exist."""
    user_cache_dir_mock.return_value = tempdir
    tempdir = Path(tempdir)
    tempdir.rmdir()
    assert not tempdir.exists()
    cache.CacheStore()
    assert tempdir.exists()


@mock.patch("requests.get")
@mock.patch("appdirs.user_cache_dir")
def test_cache_read_csv(user_cache_dir_mock, http_get_mock, tempdir):
    user_cache_dir_mock.return_value = tempdir
    resp = mock.Mock()
    http_get_mock.return_value = resp
    resp.content = b"col_a,col_b\n1,blue\n2,red\n"
    store = cache.CacheStore()
    url = "http://blah.invalid/erddap/search?q=bacon+egg+and+cheese"
    df = store.read_csv(url)
    assert len(df) == 2
    filepath = store.cache_file(url)
    with gzip.open(filepath, "wb") as f:
        f.write(b"col_a,col_b\n3,green\n4,yellow\n")
    df = store.read_csv(url)
    assert df["col_a"].tolist() == [3, 4]
    assert df["col_b"].tolist() == ["green", "yellow"]

    # Force a cache miss
    now = time.time()
    os.utime(filepath, (now - 1000, now - 1000))
    df = store.read_csv(url)
    assert df["col_a"].tolist() == [1, 2]
    assert df["col_b"].tolist() == ["blue", "red"]


@mock.patch("requests.get")
@mock.patch("appdirs.user_cache_dir")
def test_cache_read_json(user_cache_dir_mock, http_get_mock, tempdir):
    user_cache_dir_mock.return_value = tempdir
    resp = mock.Mock()
    http_get_mock.return_value = resp
    resp.content = b'{"key":"value", "example": "blah"}'
    store = cache.CacheStore()
    url = "http://blah.invalid/erddap/search?q=bacon+egg+and+cheese"
    data = store.read_json(url)
    assert data == {"key": "value", "example": "blah"}
    filepath = store.cache_file(url)
    with gzip.open(filepath, "wb") as f:
        f.write(b'{"different": "is different"}')
    data = store.read_json(url)
    assert data["different"] == "is different"

    # Force a cache miss
    now = time.time()
    os.utime(filepath, (now - 1000, now - 1000))
    data = store.read_json(url)
    assert data == {"key": "value", "example": "blah"}
