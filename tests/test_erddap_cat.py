#!/usr/bin/env pytest
"""Unit tests."""
from unittest import mock
from urllib.parse import parse_qsl, urlparse

import cf_pandas
import intake
import pandas as pd
import pytest

from erddapy import ERDDAP

from intake_erddap.erddap import GridDAPSource
from intake_erddap.erddap_cat import ERDDAPCatalog


@pytest.fixture
def single_dataset_catalog() -> pd.DataFrame:
    """Fixture returns a dataframe with a single dataset ID."""
    df = pd.DataFrame()
    df["datasetID"] = ["abc123"]
    return df


def test_nothing():
    """This test exists to ensure that at least one test works."""
    pass


@mock.patch("erddapy.ERDDAP.to_pandas")
def test_erddap_catalog(mock_to_pandas):
    """Test basic catalog API."""
    results = pd.DataFrame()
    results["datasetID"] = ["abc123"]
    mock_to_pandas.return_value = results
    server = "http://erddap.invalid/erddap"
    cat = ERDDAPCatalog(server=server)
    assert list(cat) == ["abc123"]


@mock.patch("pandas.read_csv")
def test_erddap_catalog_searching(mock_read_csv):
    """Test catalog with search parameters."""
    results = pd.DataFrame()
    results["datasetID"] = ["abc123"]
    mock_read_csv.return_value = results
    kw = {
        "min_lon": -180,
        "max_lon": -156,
        "min_lat": 50,
        "max_lat": 66,
        "min_time": "2021-4-1",
        "max_time": "2021-4-2",
    }
    server = "http://erddap.invalid/erddap"
    cat = ERDDAPCatalog(server=server, kwargs_search=kw)
    assert list(cat) == ["abc123"]


@mock.patch("pandas.read_csv")
def test_erddap_catalog_searching_variable(mock_read_csv):
    df1 = pd.DataFrame()
    df1["Category"] = ["sea_water_temperature"]
    df1["URL"] = ["http://blah.com"]
    df2 = pd.DataFrame()
    df2["Dataset ID"] = ["testID"]
    # pd.read_csv is called twice, so two return results
    mock_read_csv.side_effect = [df1, df2]
    criteria = {
        "temp": {
            "standard_name": "sea_water_temperature$",
        },
    }
    cf_pandas.set_options(custom_criteria=criteria)
    kw = {
        "min_lon": -180,
        "max_lon": -156,
        "min_lat": 50,
        "max_lat": 66,
        "min_time": "2021-4-1",
        "max_time": "2021-4-2",
    }
    server = "http://erddap.invalid/erddap"
    cat = ERDDAPCatalog(
        server=server, kwargs_search=kw, category_search=("standard_name", "temp")
    )
    assert "standard_name" in cat.kwargs_search
    assert cat.kwargs_search["standard_name"] == "sea_water_temperature"


@pytest.mark.integration
def test_ioos_erddap_catalog_and_source():
    """Integration test against IOOS Sensors ERDDAP."""
    kw = {
        "min_lon": -180,
        "max_lon": -156,
        "min_lat": 50,
        "max_lat": 66,
        "min_time": "2021-4-1",
        "max_time": "2021-4-2",
    }
    server = "https://erddap.sensors.ioos.us/erddap"
    cat_sensors = intake.open_erddap_cat(server, kwargs_search=kw)
    df = cat_sensors[list(cat_sensors)[0]].read()
    assert df is not None
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_invalid_kwarg_search():
    kw = {
        "min_lon": -180,
        "max_lon": -156,
        "max_lat": 66,
        "min_time": "2021-4-1",
        "max_time": "2021-4-2",
    }
    server = "http://erddap.sensors.ioos.us/erddap"

    with pytest.raises(ValueError):
        intake.open_erddap_cat(server, kwargs_search=kw)

    kw = {
        "min_lon": -180,
        "max_lon": -156,
        "min_lat": 50,
        "max_lat": 66,
        "max_time": "2021-4-2",
    }

    with pytest.raises(ValueError):
        intake.open_erddap_cat(server, kwargs_search=kw)


def test_catalog_uses_di_client():
    """Tests that the catalog uses the dependency injection provided client."""
    mock_erddap_client = mock.create_autospec(ERDDAP)
    server = "http://erddap.invalid/erddap"
    cat = ERDDAPCatalog(server=server, erddap_client=mock_erddap_client)
    client = cat.get_client()
    assert isinstance(client, mock.NonCallableMagicMock)


@mock.patch("erddapy.ERDDAP.to_pandas")
def test_catalog_skips_all_datasets_row(mock_to_pandas):
    """Tests that the catalog results ignore allDatasets special dataset."""
    df = pd.DataFrame()
    df["datasetID"] = ["allDatasets", "abc123"]
    mock_to_pandas.return_value = df
    server = "http://erddap.invalid/erddap"
    cat = ERDDAPCatalog(server=server)
    assert list(cat) == ["abc123"]


@mock.patch("pandas.read_csv")
def test_params_search(mock_read_csv):
    df = pd.DataFrame()
    df["datasetID"] = ["allDatasets", "abc123"]
    mock_read_csv.return_value = df
    erddap_url = "https://erddap.invalid/erddap"
    search = {
        "min_lon": -100,
        "max_lon": -54,
        "min_lat": 19,
        "max_lat": 55,
        "min_time": "2022-01-01",
        "max_time": "2022-11-07",
        "standard_name": "sea_water_temperature",
    }
    cat = ERDDAPCatalog(server=erddap_url, kwargs_search=search)
    search_url = cat.get_search_url()
    assert search_url is not None
    parts = urlparse(search_url)
    assert parts.scheme == "https"
    assert parts.hostname == "erddap.invalid"
    query = dict(parse_qsl(parts.query))
    assert query["minLon"] == "-100"
    assert int(float(query["minTime"])) == 1640995200
    assert query["standard_name"] == "sea_water_temperature"


@mock.patch("pandas.read_csv")
def test_constraints_present_in_source(mock_read_csv, single_dataset_catalog):
    mock_read_csv.return_value = single_dataset_catalog
    server = "https://erddap.invalid/erddap"
    search = {
        "min_time": "2022-01-01",
        "max_time": "2022-11-07",
    }
    cat = ERDDAPCatalog(server=server, kwargs_search=search)
    source = next(cat.values())
    assert source._constraints["time>="] == "2022-01-01"
    assert source._constraints["time<="] == "2022-11-07"

    cat = ERDDAPCatalog(
        server=server, kwargs_search=search, use_source_constraints=False
    )
    source = next(cat.values())
    assert len(source._constraints) == 0


@mock.patch("pandas.read_csv")
def test_catalog_with_griddap(mock_read_csv, single_dataset_catalog):
    mock_read_csv.return_value = single_dataset_catalog
    server = "https://erddap.invalid/erddap"
    search = {
        "min_time": "2022-01-01",
        "max_time": "2022-11-07",
    }
    cat = ERDDAPCatalog(server=server, kwargs_search=search, protocol="griddap")
    source = next(cat.values())
    assert isinstance(source, GridDAPSource)


@mock.patch("pandas.read_csv")
def test_catalog_with_unsupported_protocol(mock_read_csv, single_dataset_catalog):
    server = "https://erddap.invalid/erddap"
    search = {
        "min_time": "2022-01-01",
        "max_time": "2022-11-07",
    }
    mock_read_csv.return_value = single_dataset_catalog
    with pytest.raises(ValueError):
        ERDDAPCatalog(server=server, kwargs_search=search, protocol="fakedap")
