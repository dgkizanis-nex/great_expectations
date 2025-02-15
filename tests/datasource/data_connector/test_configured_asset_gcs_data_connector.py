from unittest import mock

import pytest

import great_expectations.exceptions as gx_exceptions
from great_expectations.compatibility import google
from great_expectations.core import IDDict
from great_expectations.core.batch import (
    BatchRequest,
    BatchRequestBase,
    LegacyBatchDefinition,
)
from great_expectations.core.yaml_handler import YAMLHandler
from great_expectations.data_context.util import instantiate_class_from_config
from great_expectations.datasource.data_connector import ConfiguredAssetGCSDataConnector
from great_expectations.execution_engine import PandasExecutionEngine

yaml = YAMLHandler()


if not google.storage:
    pytest.skip(
        'Could not import "storage" from google.cloud in configured_asset_gcs_data_connector.py',
        allow_module_level=True,
    )

# module level markers
pytestmark = pytest.mark.big


@pytest.fixture
def expected_config_dict():
    """Used to validate `self_check()` and `test_yaml_config()` outputs."""
    config = {
        "class_name": "ConfiguredAssetGCSDataConnector",
        "data_asset_count": 1,
        "example_data_asset_names": [
            "alpha",
        ],
        "data_assets": {
            "alpha": {
                "example_data_references": [
                    "alpha-1.csv",
                    "alpha-2.csv",
                    "alpha-3.csv",
                ],
                "batch_definition_count": 3,
            },
        },
        "example_unmatched_data_references": [],
        "unmatched_data_reference_count": 0,
    }
    return config


@pytest.fixture
def expected_batch_definitions_unsorted():
    """
    Used to validate `get_batch_definition_list_from_batch_request()` outputs.
    Input and output should maintain the same order (henced "unsorted")
    """
    expected = [
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "alex", "timestamp": "20200809", "price": "1000"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "eugene", "timestamp": "20200809", "price": "1500"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200811", "price": "1009"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "abe", "timestamp": "20200809", "price": "1040"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "will", "timestamp": "20200809", "price": "1002"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200713", "price": "1567"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "eugene", "timestamp": "20201129", "price": "1900"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "will", "timestamp": "20200810", "price": "1001"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200810", "price": "1003"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "alex", "timestamp": "20200819", "price": "1300"}),
        ),
    ]
    return expected


@pytest.fixture
def expected_batch_definitions_sorted():
    """
    Used to validate `get_batch_definition_list_from_batch_request()` outputs.
    Input should be sorted based on some criteria, resulting in some change
    between input and output.
    """
    expected = [
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "abe", "timestamp": "20200809", "price": "1040"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "alex", "timestamp": "20200819", "price": "1300"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "alex", "timestamp": "20200809", "price": "1000"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "eugene", "timestamp": "20201129", "price": "1900"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "eugene", "timestamp": "20200809", "price": "1500"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200811", "price": "1009"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200810", "price": "1003"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "james", "timestamp": "20200713", "price": "1567"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "will", "timestamp": "20200810", "price": "1001"}),
        ),
        LegacyBatchDefinition(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
            batch_identifiers=IDDict({"name": "will", "timestamp": "20200809", "price": "1002"}),
        ),
    ]
    return expected


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
    return_value=["alpha-1.csv", "alpha-2.csv", "alpha-3.csv"],
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_instantiation_without_args(mock_gcs_conn, mock_list_keys, expected_config_dict):
    my_data_connector = ConfiguredAssetGCSDataConnector(
        name="my_data_connector",
        datasource_name="FAKE_DATASOURCE_NAME",
        execution_engine=PandasExecutionEngine(),
        default_regex={
            "pattern": "alpha-(.*)\\.csv",
            "group_names": ["index"],
        },
        bucket_or_name="my_bucket",
        prefix="",
        assets={"alpha": {}},
    )

    my_data_connector._refresh_data_references_cache()
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_unmatched_data_references() == []


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
    return_value=["alpha-1.csv", "alpha-2.csv", "alpha-3.csv"],
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.service_account.Credentials.from_service_account_file"
)
def test_instantiation_with_filename_arg(
    mock_auth_method, mock_gcs_conn, mock_list_keys, expected_config_dict
):
    my_data_connector = ConfiguredAssetGCSDataConnector(
        name="my_data_connector",
        datasource_name="FAKE_DATASOURCE_NAME",
        execution_engine=PandasExecutionEngine(),
        gcs_options={
            "filename": "my_filename.json",
        },
        default_regex={
            "pattern": "alpha-(.*)\\.csv",
            "group_names": ["index"],
        },
        bucket_or_name="my_bucket",
        prefix="",
        assets={"alpha": {}},
    )

    my_data_connector._refresh_data_references_cache()
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_unmatched_data_references() == []


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
    return_value=["alpha-1.csv", "alpha-2.csv", "alpha-3.csv"],
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.service_account.Credentials.from_service_account_info"
)
def test_instantiation_with_info_arg(
    mock_auth_method, mock_gcs_conn, mock_list_keys, expected_config_dict
):
    my_data_connector = ConfiguredAssetGCSDataConnector(
        name="my_data_connector",
        datasource_name="FAKE_DATASOURCE_NAME",
        execution_engine=PandasExecutionEngine(),
        gcs_options={
            "info": "{ my_json: my_content }",
        },
        default_regex={
            "pattern": "alpha-(.*)\\.csv",
            "group_names": ["index"],
        },
        bucket_or_name="my_bucket",
        prefix="",
        assets={"alpha": {}},
    )

    my_data_connector._refresh_data_references_cache()
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_unmatched_data_references() == []


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
    return_value=["alpha-1.csv", "alpha-2.csv", "alpha-3.csv"],
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_get_batch_definition_list_from_batch_request_with_nonexistent_datasource_name_raises_error(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector = ConfiguredAssetGCSDataConnector(
        name="my_data_connector",
        datasource_name="FAKE_DATASOURCE_NAME",
        execution_engine=PandasExecutionEngine(),
        default_regex={
            "pattern": "alpha-(.*)\\.csv",
            "group_names": ["index"],
        },
        bucket_or_name="my_bucket",
        prefix="",
        assets={"alpha": {}},
    )

    # Raises error in `DataConnector._validate_batch_request()` due to `datasource_name` in BatchRequest not matching DataConnector `datasource_name`  # noqa: E501
    with pytest.raises(ValueError):
        my_data_connector.get_batch_definition_list_from_batch_request(
            BatchRequest(
                datasource_name="something",
                data_connector_name="my_data_connector",
                data_asset_name="something",
            )
        )


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@pytest.mark.slow  # 1.65s
def test_get_definition_list_from_batch_request_with_empty_args_raises_error(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector_yaml = yaml.load(
        """
           class_name: ConfiguredAssetGCSDataConnector
           datasource_name: test_environment
           bucket_or_name: my_bucket
           prefix: ""
           assets:
               TestFiles:
           default_regex:
               pattern: (.+)_(.+)_(.+)\\.csv
               group_names:
                   - name
                   - timestamp
                   - price
       """,
    )

    mock_list_keys.return_value = (
        [
            "alex_20200809_1000.csv",
            "eugene_20200809_1500.csv",
            "james_20200811_1009.csv",
            "abe_20200809_1040.csv",
            "will_20200809_1002.csv",
            "james_20200713_1567.csv",
            "eugene_20201129_1900.csv",
            "will_20200810_1001.csv",
            "james_20200810_1003.csv",
            "alex_20200819_1300.csv",
        ],
    )

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    # Raises error in `FilePathDataConnector.get_batch_definition_list_from_batch_request()` due to missing a `batch_request` arg  # noqa: E501
    with pytest.raises(TypeError):
        # noinspection PyArgumentList
        my_data_connector.get_batch_definition_list_from_batch_request()


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_get_definition_list_from_batch_request_with_unnamed_data_asset_name_raises_error(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector_yaml = yaml.load(
        """
           class_name: ConfiguredAssetGCSDataConnector
           datasource_name: test_environment
           bucket_or_name: my_bucket
           prefix: ""
           assets:
               TestFiles:
           default_regex:
               pattern: (.+)_(.+)_(.+)\\.csv
               group_names:
                   - name
                   - timestamp
                   - price
       """,
    )

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    # Raises error in `Batch._validate_init_parameters()` due to `data_asset_name` being `NoneType` and not the required `str`  # noqa: E501
    with pytest.raises(TypeError):
        my_data_connector.get_batch_definition_list_from_batch_request(
            BatchRequest(
                datasource_name="test_environment",
                data_connector_name="general_gcs_data_connector",
                data_asset_name="",
            )
        )


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_return_all_batch_definitions_unsorted_without_named_data_asset_name(
    mock_gcs_conn,
    mock_list_keys,
    empty_data_context_stats_enabled,
    expected_batch_definitions_unsorted,
):
    my_data_connector_yaml = yaml.load(
        """
           class_name: ConfiguredAssetGCSDataConnector
           datasource_name: test_environment
           bucket_or_name: my_bucket
           prefix: ""
           assets:
               TestFiles:
           default_regex:
               pattern: (.+)_(.+)_(.+)\\.csv
               group_names:
                   - name
                   - timestamp
                   - price
       """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    # In an actual production environment, GCS will automatically sort these blobs by path (alphabetic order).  # noqa: E501
    # Source: https://cloud.google.com/storage/docs/listing-objects
    #
    # The expected behavior is that our `unsorted_batch_definition_list` will maintain the same order it parses through `list_gcs_keys()` (hence "unsorted").  # noqa: E501
    # When using an actual `Client` (and not a mock), the output of `list_gcs_keys` would be pre-sorted by nature of how the system orders blobs.  # noqa: E501
    # It is important to note that although this is a minor deviation, it is deemed to be immaterial as we still end up testing our desired behavior.  # noqa: E501

    unsorted_batch_definition_list = (
        my_data_connector._get_batch_definition_list_from_batch_request(
            BatchRequestBase(
                datasource_name="test_environment",
                data_connector_name="general_gcs_data_connector",
                data_asset_name="",
            )
        )
    )
    assert unsorted_batch_definition_list == expected_batch_definitions_unsorted


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_return_all_batch_definitions_unsorted_with_named_data_asset_name(
    mock_gcs_conn,
    mock_list_keys,
    empty_data_context_stats_enabled,
    expected_batch_definitions_unsorted,
):
    my_data_connector_yaml = yaml.load(
        """
           class_name: ConfiguredAssetGCSDataConnector
           datasource_name: test_environment
           bucket_or_name: my_bucket
           prefix: ""
           assets:
               TestFiles:
           default_regex:
               pattern: (.+)_(.+)_(.+)\\.csv
               group_names:
                   - name
                   - timestamp
                   - price
       """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    # In an actual production environment, GCS will automatically sort these blobs by path (alphabetic order).  # noqa: E501
    # Source: https://cloud.google.com/storage/docs/listing-objects
    #
    # The expected behavior is that our `unsorted_batch_definition_list` will maintain the same order it parses through `list_gcs_keys()` (hence "unsorted").  # noqa: E501
    # When using an actual `Client` (and not a mock), the output of `list_gcs_keys` would be pre-sorted by nature of how the system orders blobs.  # noqa: E501
    # It is important to note that although this is a minor deviation, it is deemed to be immaterial as we still end up testing our desired behavior.  # noqa: E501

    unsorted_batch_definition_list = my_data_connector.get_batch_definition_list_from_batch_request(
        BatchRequest(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
        )
    )
    assert unsorted_batch_definition_list == expected_batch_definitions_unsorted


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_return_all_batch_definitions_basic_sorted(
    mock_gcs_conn,
    mock_list_keys,
    empty_data_context_stats_enabled,
    expected_batch_definitions_sorted,
):
    my_data_connector_yaml = yaml.load(
        """
       class_name: ConfiguredAssetGCSDataConnector
       datasource_name: test_environment
       bucket_or_name: my_bucket
       prefix: ""
       assets:
           TestFiles:
       default_regex:
           pattern: (.+)_(.+)_(.+)\\.csv
           group_names:
               - name
               - timestamp
               - price
       sorters:
           - orderby: asc
             class_name: LexicographicSorter
             name: name
           - datetime_format: "%Y%m%d"
             orderby: desc
             class_name: DateTimeSorter
             name: timestamp
           - orderby: desc
             class_name: NumericSorter
             name: price
     """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    sorted_batch_definition_list = my_data_connector.get_batch_definition_list_from_batch_request(
        BatchRequest(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
        )
    )
    assert sorted_batch_definition_list == expected_batch_definitions_sorted


@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
def test_return_all_batch_definitions_returns_specified_partition(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector_yaml = yaml.load(
        """
       class_name: ConfiguredAssetGCSDataConnector
       datasource_name: test_environment
       bucket_or_name: my_bucket
       prefix: ""
       assets:
           TestFiles:
       default_regex:
           pattern: (.+)_(.+)_(.+)\\.csv
           group_names:
               - name
               - timestamp
               - price
       sorters:
           - orderby: asc
             class_name: LexicographicSorter
             name: name
           - datetime_format: "%Y%m%d"
             orderby: desc
             class_name: DateTimeSorter
             name: timestamp
           - orderby: desc
             class_name: NumericSorter
             name: price
     """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    my_batch_request: BatchRequest = BatchRequest(
        datasource_name="test_environment",
        data_connector_name="general_gcs_data_connector",
        data_asset_name="TestFiles",
        data_connector_query=IDDict(
            **{
                "batch_filter_parameters": {
                    "name": "james",
                    "timestamp": "20200713",
                    "price": "1567",
                }
            }
        ),
    )

    my_batch_definition_list = my_data_connector.get_batch_definition_list_from_batch_request(
        batch_request=my_batch_request
    )

    assert len(my_batch_definition_list) == 1
    my_batch_definition = my_batch_definition_list[0]
    expected_batch_definition = LegacyBatchDefinition(
        datasource_name="test_environment",
        data_connector_name="general_gcs_data_connector",
        data_asset_name="TestFiles",
        batch_identifiers=IDDict(
            **{
                "name": "james",
                "timestamp": "20200713",
                "price": "1567",
            }
        ),
    )
    assert my_batch_definition == expected_batch_definition


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
def test_return_all_batch_definitions_sorted_without_data_connector_query(
    mock_gcs_conn,
    mock_list_keys,
    empty_data_context_stats_enabled,
    expected_batch_definitions_sorted,
):
    my_data_connector_yaml = yaml.load(
        """
       class_name: ConfiguredAssetGCSDataConnector
       datasource_name: test_environment
       bucket_or_name: my_bucket
       prefix: ""
       assets:
           TestFiles:
       default_regex:
           pattern: (.+)_(.+)_(.+)\\.csv
           group_names:
               - name
               - timestamp
               - price
       sorters:
           - orderby: asc
             class_name: LexicographicSorter
             name: name
           - datetime_format: "%Y%m%d"
             orderby: desc
             class_name: DateTimeSorter
             name: timestamp
           - orderby: desc
             class_name: NumericSorter
             name: price
     """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config=my_data_connector_yaml,
        runtime_environment={
            "name": "general_gcs_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
    )

    sorted_batch_definition_list = my_data_connector.get_batch_definition_list_from_batch_request(
        BatchRequest(
            datasource_name="test_environment",
            data_connector_name="general_gcs_data_connector",
            data_asset_name="TestFiles",
        )
    )
    assert sorted_batch_definition_list == expected_batch_definitions_sorted


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
def test_return_all_batch_definitions_raises_error_due_to_sorter_that_does_not_match_group(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector_yaml = yaml.load(
        """
       class_name: ConfiguredAssetGCSDataConnector
       datasource_name: test_environment
       bucket_or_name: my_bucket
       assets:
           TestFiles:
               pattern: (.+)_(.+)_(.+)\\.csv
               group_names:
                   - name
                   - timestamp
                   - price
       default_regex:
           pattern: (.+)_.+_.+\\.csv
           group_names:
               - name
       sorters:
           - orderby: asc
             class_name: LexicographicSorter
             name: name
           - datetime_format: "%Y%m%d"
             orderby: desc
             class_name: DateTimeSorter
             name: timestamp
           - orderby: desc
             class_name: NumericSorter
             name: for_me_Me_Me
   """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    # Raises error due to a sorter (for_me_Me_me) not matching a group_name in `FilePathDataConnector._validate_sorters_configuration()`  # noqa: E501
    with pytest.raises(gx_exceptions.DataConnectorError):
        instantiate_class_from_config(
            config=my_data_connector_yaml,
            runtime_environment={
                "name": "general_gcs_data_connector",
                "execution_engine": PandasExecutionEngine(),
            },
            config_defaults={"module_name": "great_expectations.datasource.data_connector"},
        )


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys"
)
def test_return_all_batch_definitions_too_many_sorters(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    my_data_connector_yaml = yaml.load(
        """
       class_name: ConfiguredAssetGCSDataConnector
       datasource_name: test_environment
       bucket_or_name: my_bucket
       prefix: ""
       assets:
           TestFiles:
       default_regex:
           pattern: (.+)_.+_.+\\.csv
           group_names:
               - name
       sorters:
           - orderby: asc
             class_name: LexicographicSorter
             name: name
           - datetime_format: "%Y%m%d"
             orderby: desc
             class_name: DateTimeSorter
             name: timestamp
           - orderby: desc
             class_name: NumericSorter
             name: price
   """,
    )

    mock_list_keys.return_value = [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]

    # Raises error due to a non-existent sorter being specified in `FilePathDataConnector._validate_sorters_configuration()`  # noqa: E501
    with pytest.raises(gx_exceptions.DataConnectorError):
        instantiate_class_from_config(
            config=my_data_connector_yaml,
            runtime_environment={
                "name": "general_gcs_data_connector",
                "execution_engine": PandasExecutionEngine(),
            },
            config_defaults={"module_name": "great_expectations.datasource.data_connector"},
        )


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
)
def test_example_with_explicit_data_asset_names(
    mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled
):
    yaml_string = """
class_name: ConfiguredAssetGCSDataConnector
datasource_name: FAKE_DATASOURCE_NAME
bucket_or_name: my_bucket
prefix: my_base_directory/
default_regex:
   pattern: ^(.+)-(\\d{4})(\\d{2})\\.(csv|txt)$
   group_names:
       - data_asset_name
       - year_dir
       - month_dir
assets:
   alpha:
       prefix: my_base_directory/alpha/files/go/here/
       pattern: ^(.+)-(\\d{4})(\\d{2})\\.csv$
   beta:
       prefix: my_base_directory/beta_here/
       pattern: ^(.+)-(\\d{4})(\\d{2})\\.txt$
   gamma:
       pattern: ^(.+)-(\\d{4})(\\d{2})\\.csv$
   """
    config = yaml.load(yaml_string)

    mock_list_keys.return_value = [  # Initial return value during instantiation
        "my_base_directory/alpha/files/go/here/alpha-202001.csv",
        "my_base_directory/alpha/files/go/here/alpha-202002.csv",
        "my_base_directory/alpha/files/go/here/alpha-202003.csv",
        "my_base_directory/beta_here/beta-202001.txt",
        "my_base_directory/beta_here/beta-202002.txt",
        "my_base_directory/beta_here/beta-202003.txt",
        "my_base_directory/beta_here/beta-202004.txt",
        "my_base_directory/gamma-202001.csv",
        "my_base_directory/gamma-202002.csv",
        "my_base_directory/gamma-202003.csv",
        "my_base_directory/gamma-202004.csv",
        "my_base_directory/gamma-202005.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config,
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
        runtime_environment={
            "name": "my_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
    )

    # Since we are using mocks, we need to redefine the output of subsequent calls to `list_gcs_keys()`  # noqa: E501
    # Our patched object provides the ability to define a "side_effect", an iterable containing return  # noqa: E501
    # values for subsequent calls. Since `_refresh_data_references_cache()` makes multiple calls to
    # this method (once per asset), we define our expected behavior below.
    #
    # Source: https://stackoverflow.com/questions/24897145/python-mock-multiple-return-values

    mock_list_keys.side_effect = [
        [  # Asset alpha
            "my_base_directory/alpha/files/go/here/alpha-202001.csv",
            "my_base_directory/alpha/files/go/here/alpha-202002.csv",
            "my_base_directory/alpha/files/go/here/alpha-202003.csv",
        ],
        [  # Asset beta
            "my_base_directory/beta_here/beta-202001.txt",
            "my_base_directory/beta_here/beta-202002.txt",
            "my_base_directory/beta_here/beta-202003.txt",
            "my_base_directory/beta_here/beta-202004.txt",
        ],
        [  # Asset gamma
            "my_base_directory/gamma-202001.csv",
            "my_base_directory/gamma-202002.csv",
            "my_base_directory/gamma-202003.csv",
            "my_base_directory/gamma-202004.csv",
            "my_base_directory/gamma-202005.csv",
        ],
    ]

    my_data_connector._refresh_data_references_cache()

    assert len(my_data_connector.get_unmatched_data_references()) == 0

    assert (
        len(
            my_data_connector.get_batch_definition_list_from_batch_request(
                batch_request=BatchRequest(
                    datasource_name="FAKE_DATASOURCE_NAME",
                    data_connector_name="my_data_connector",
                    data_asset_name="alpha",
                )
            )
        )
        == 3
    )

    assert (
        len(
            my_data_connector.get_batch_definition_list_from_batch_request(
                batch_request=BatchRequest(
                    datasource_name="FAKE_DATASOURCE_NAME",
                    data_connector_name="my_data_connector",
                    data_asset_name="beta",
                )
            )
        )
        == 4
    )

    assert (
        len(
            my_data_connector.get_batch_definition_list_from_batch_request(
                batch_request=BatchRequest(
                    datasource_name="FAKE_DATASOURCE_NAME",
                    data_connector_name="my_data_connector",
                    data_asset_name="gamma",
                )
            )
        )
        == 5
    )


# noinspection PyUnusedLocal
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.google.storage.Client"
)
@mock.patch(
    "great_expectations.datasource.data_connector.configured_asset_gcs_data_connector.list_gcs_keys",
)
def test_get_full_file_path(mock_gcs_conn, mock_list_keys, empty_data_context_stats_enabled):
    yaml_string = """
class_name: ConfiguredAssetGCSDataConnector
datasource_name: FAKE_DATASOURCE_NAME
bucket_or_name: my_bucket
prefix: my_base_directory/
default_regex:
   pattern: ^(.+)-(\\d{{4}})(\\d{{2}})\\.(csv|txt)$
   group_names:
       - data_asset_name
       - year_dir
       - month_dir
assets:
   alpha:
       prefix: my_base_directory/alpha/files/go/here/
       pattern: ^(.+)-(\\d{{4}})(\\d{{2}})\\.csv$
   beta:
       prefix: my_base_directory/beta_here/
       pattern: ^(.+)-(\\d{{4}})(\\d{{2}})\\.txt$
   gamma:
       pattern: ^(.+)-(\\d{{4}})(\\d{{2}})\\.csv$
   """
    config = yaml.load(yaml_string)

    mock_list_keys.return_value = [
        "my_base_directory/alpha/files/go/here/alpha-202001.csv",
        "my_base_directory/alpha/files/go/here/alpha-202002.csv",
        "my_base_directory/alpha/files/go/here/alpha-202003.csv",
        "my_base_directory/beta_here/beta-202001.txt",
        "my_base_directory/beta_here/beta-202002.txt",
        "my_base_directory/beta_here/beta-202003.txt",
        "my_base_directory/beta_here/beta-202004.txt",
        "my_base_directory/gamma-202001.csv",
        "my_base_directory/gamma-202002.csv",
        "my_base_directory/gamma-202003.csv",
        "my_base_directory/gamma-202004.csv",
        "my_base_directory/gamma-202005.csv",
    ]

    my_data_connector: ConfiguredAssetGCSDataConnector = instantiate_class_from_config(
        config,
        config_defaults={"module_name": "great_expectations.datasource.data_connector"},
        runtime_environment={
            "name": "my_data_connector",
            "execution_engine": PandasExecutionEngine(),
        },
    )

    assert (
        my_data_connector._get_full_file_path(
            "my_base_directory/alpha/files/go/here/alpha-202001.csv", "alpha"
        )
        == "gs://my_bucket/my_base_directory/alpha/files/go/here/alpha-202001.csv"
    )
    assert (
        my_data_connector._get_full_file_path("my_base_directory/beta_here/beta-202002.txt", "beta")
        == "gs://my_bucket/my_base_directory/beta_here/beta-202002.txt"
    )
    assert (
        my_data_connector._get_full_file_path("my_base_directory/gamma-202005.csv", "gamma")
        == "gs://my_bucket/my_base_directory/gamma-202005.csv"
    )
