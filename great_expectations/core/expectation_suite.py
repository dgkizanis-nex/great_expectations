from __future__ import annotations

import datetime
import json
import logging
import pprint
import uuid
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from marshmallow import Schema, ValidationError, fields, post_dump, post_load, pre_dump

import great_expectations as gx
import great_expectations.exceptions as gx_exceptions
from great_expectations import __version__ as ge_version
from great_expectations._docs_decorators import (
    public_api,
)
from great_expectations.analytics.anonymizer import anonymize
from great_expectations.analytics.client import submit as submit_event
from great_expectations.analytics.events import (
    ExpectationSuiteExpectationCreatedEvent,
    ExpectationSuiteExpectationDeletedEvent,
    ExpectationSuiteExpectationUpdatedEvent,
)
from great_expectations.compatibility.typing_extensions import override
from great_expectations.core.evaluation_parameters import (
    _deduplicate_evaluation_parameter_dependencies,
)
from great_expectations.core.metric_domain_types import MetricDomainTypes
from great_expectations.core.serdes import _IdentifierBundle
from great_expectations.core.util import (
    convert_to_json_serializable,
    ensure_json_serializable,
    nested_update,
    parse_string_to_datetime,
)
from great_expectations.render import (
    AtomicPrescriptiveRendererType,
    RenderedAtomicContent,
)
from great_expectations.types import SerializableDictDot
from great_expectations.util import deep_filter_properties_iterable

if TYPE_CHECKING:
    from great_expectations.alias_types import JSONValues
    from great_expectations.execution_engine import ExecutionEngine
    from great_expectations.expectations.expectation import Expectation
    from great_expectations.expectations.expectation_configuration import (
        ExpectationConfiguration,
    )

    _TExpectation = TypeVar("_TExpectation", bound=Expectation)

logger = logging.getLogger(__name__)


@public_api
class ExpectationSuite(SerializableDictDot):
    """Set-like collection of Expectations.

    Args:
        name: Name of the Expectation Suite
        expectations: Expectation Configurations to associate with this Expectation Suite.
        evaluation_parameters: Evaluation parameters to be substituted when evaluating Expectations.
        execution_engine_type: Name of the execution engine type.
        meta: Metadata related to the suite.
        id: Great Expectations Cloud id for this Expectation Suite.
    """

    def __init__(  # noqa: PLR0913
        self,
        name: Optional[str] = None,
        expectations: Optional[Sequence[Union[dict, ExpectationConfiguration, Expectation]]] = None,
        evaluation_parameters: Optional[dict] = None,
        execution_engine_type: Optional[Type[ExecutionEngine]] = None,
        meta: Optional[dict] = None,
        notes: str | list[str] | None = None,
        id: Optional[str] = None,
    ) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("name must be provided as a non-empty string")  # noqa: TRY003
        self.name = name
        self.id = id

        self.expectations = [self._process_expectation(exp) for exp in expectations or []]

        if evaluation_parameters is None:
            evaluation_parameters = {}
        self.evaluation_parameters = evaluation_parameters
        self.execution_engine_type = execution_engine_type
        if meta is None:
            meta = {"great_expectations_version": ge_version}
        if (
            "great_expectations.__version__" not in meta.keys()
            and "great_expectations_version" not in meta.keys()
        ):
            meta["great_expectations_version"] = ge_version
        # We require meta information to be serializable, but do not convert until necessary
        ensure_json_serializable(meta)
        self.meta = meta
        self.notes = notes

        from great_expectations import project_manager

        self._store = project_manager.get_expectations_store()

    @property
    def evaluation_parameter_options(self) -> tuple[str, ...]:
        """EvaluationParameter options for this ExpectationSuite.

        Returns:
            tuple[str, ...]: The keys of the evaluation parameters used by all Expectations of this suite at runtime.
        """  # noqa: E501
        output: set[str] = set()
        for expectation in self.expectations:
            output.update(expectation.evaluation_parameter_options)
        return tuple(sorted(output))

    @public_api
    def add_expectation(self, expectation: _TExpectation) -> _TExpectation:
        """Add an Expectation to the collection."""
        if expectation.id:
            raise RuntimeError(  # noqa: TRY003
                "Cannot add Expectation because it already belongs to an ExpectationSuite. "
                "If you want to update an existing Expectation, please call Expectation.save(). "
                "If you are copying this Expectation to a new ExpectationSuite, please copy "
                "it first (the core expectations and some others support copy(expectation)) "
                "and set `Expectation.id = None`."
            )
        should_save_expectation = self._has_been_saved()
        expectation_is_unique = all(
            expectation.configuration != existing_expectation.configuration
            for existing_expectation in self.expectations
        )
        if expectation_is_unique:
            # suite is a set-like collection, so don't add if it not unique
            self.expectations.append(expectation)
            if should_save_expectation:
                try:
                    expectation = self._store.add_expectation(suite=self, expectation=expectation)
                    self.expectations[-1].id = expectation.id
                except Exception as exc:
                    self.expectations.pop()
                    raise exc  # noqa: TRY201

        expectation.register_save_callback(save_callback=self._save_expectation)

        self._submit_expectation_created_event(expectation=expectation)

        return expectation

    def _submit_expectation_created_event(self, expectation: Expectation) -> None:
        if expectation.__module__.startswith("great_expectations."):
            custom_exp_type = False
            expectation_type = expectation.expectation_type
        else:
            custom_exp_type = True
            expectation_type = anonymize(expectation.expectation_type)

        submit_event(
            event=ExpectationSuiteExpectationCreatedEvent(
                expectation_id=expectation.id,
                expectation_suite_id=self.id,
                expectation_type=expectation_type,
                custom_exp_type=custom_exp_type,
            )
        )

    def _process_expectation(
        self, expectation_like: Union[Expectation, ExpectationConfiguration, dict]
    ) -> Expectation:
        """Transform an Expectation from one of its various serialized forms to the Expectation type,
        and bind it to this ExpectationSuite.

        Raises:
            ValueError: If expectation_like is of type Expectation and expectation_like.id is not None.
        """  # noqa: E501
        from great_expectations.expectations.expectation import Expectation
        from great_expectations.expectations.expectation_configuration import (
            ExpectationConfiguration,
        )

        if isinstance(expectation_like, Expectation):
            if expectation_like.id:
                raise ValueError(  # noqa: TRY003
                    "Expectations in parameter `expectations` must not belong to another ExpectationSuite. "  # noqa: E501
                    "Instead, please use copies of Expectations, by calling `copy.copy(expectation)`."  # noqa: E501
                )
            expectation_like.register_save_callback(save_callback=self._save_expectation)
            return expectation_like
        elif isinstance(expectation_like, ExpectationConfiguration):
            return self._build_expectation(expectation_configuration=expectation_like)
        elif isinstance(expectation_like, dict):
            return self._build_expectation(
                expectation_configuration=ExpectationConfiguration(**expectation_like)
            )
        else:
            raise TypeError(  # noqa: TRY003
                f"Expected Expectation, ExpectationConfiguration, or dict, but received type {type(expectation_like)}."  # noqa: E501
            )

    @public_api
    def delete_expectation(self, expectation: Expectation) -> Expectation:
        """Delete an Expectation from the collection.

        Raises:
            KeyError: Expectation not found in suite.
        """
        remaining_expectations = [
            exp for exp in self.expectations if exp.configuration != expectation.configuration
        ]
        if len(remaining_expectations) != len(self.expectations) - 1:
            raise KeyError("No matching expectation was found.")  # noqa: TRY003
        self.expectations = remaining_expectations

        if self._has_been_saved():
            # only persist on delete if the suite has already been saved
            try:
                self._store.delete_expectation(suite=self, expectation=expectation)
            except Exception as exc:
                # rollback this change
                # expectation suite is set-like so order of expectations doesn't matter
                self.expectations.append(expectation)
                raise exc  # noqa: TRY201

        submit_event(
            event=ExpectationSuiteExpectationDeletedEvent(
                expectation_id=expectation.id,
                expectation_suite_id=self.id,
            )
        )

        return expectation

    @public_api
    def save(self) -> None:
        """Save this ExpectationSuite."""
        # TODO: Need to emit an event from here - we've opted out of an ExpectationSuiteUpdated event for now  # noqa: E501
        key = self._store.get_key(name=self.name, id=self.id)
        self._store.update(key=key, value=self)

    def _has_been_saved(self) -> bool:
        """Has this ExpectationSuite been persisted to a Store?"""
        # todo: this should only check local keys instead of potentially querying the remote backend
        key = self._store.get_key(name=self.name, id=self.id)
        return self._store.has_key(key=key)

    def _save_expectation(self, expectation) -> Expectation:
        expectation = self._store.update_expectation(suite=self, expectation=expectation)
        submit_event(
            event=ExpectationSuiteExpectationUpdatedEvent(
                expectation_id=expectation.id, expectation_suite_id=self.id
            )
        )
        return expectation

    @property
    def expectation_configurations(self) -> list[ExpectationConfiguration]:
        return [exp.configuration for exp in self.expectations]

    @expectation_configurations.setter
    def expectation_configurations(self, value):
        raise AttributeError(  # noqa: TRY003
            "Cannot set ExpectationSuite.expectation_configurations. "
            "Please use ExpectationSuite.expectations instead."
        )

    def add_citation(  # noqa: PLR0913
        self,
        comment: str,
        batch_request: Optional[Union[str, Dict[str, Union[str, Dict[str, Any]]]]] = None,
        batch_definition: Optional[dict] = None,
        batch_spec: Optional[dict] = None,
        batch_kwargs: Optional[dict] = None,
        batch_markers: Optional[dict] = None,
        batch_parameters: Optional[dict] = None,
        profiler_config: Optional[dict] = None,
        citation_date: Optional[Union[str, datetime.datetime]] = None,
    ) -> None:
        if "citations" not in self.meta:
            self.meta["citations"] = []

        citation_date_obj: datetime.datetime
        _citation_date_types = (type(None), str, datetime.datetime)

        if citation_date is None:
            citation_date_obj = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(citation_date, str):
            citation_date_obj = parse_string_to_datetime(datetime_string=citation_date)
        elif isinstance(citation_date, datetime.datetime):
            citation_date_obj = citation_date
        else:
            raise gx_exceptions.GreatExpectationsTypeError(  # noqa: TRY003
                f"citation_date should be of type - {' '.join(str(t) for t in _citation_date_types)}"  # noqa: E501
            )

        citation: Dict[str, Any] = {
            "citation_date": citation_date_obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "batch_request": batch_request,
            "batch_definition": batch_definition,
            "batch_spec": batch_spec,
            "batch_kwargs": batch_kwargs,
            "batch_markers": batch_markers,
            "batch_parameters": batch_parameters,
            "profiler_config": profiler_config,
            "comment": comment,
        }
        gx.util.filter_properties_dict(properties=citation, clean_falsy=True, inplace=True)
        self.meta["citations"].append(citation)

    # noinspection PyPep8Naming
    def isEquivalentTo(self, other):
        """
        ExpectationSuite equivalence relies only on expectations and evaluation parameters. It does not include:
        - data_asset_name
        - name
        - meta
        """  # noqa: E501
        if not isinstance(other, self.__class__):
            if isinstance(other, dict):
                try:
                    # noinspection PyNoneFunctionAssignment,PyTypeChecker
                    other_dict: dict = expectationSuiteSchema.load(other)
                    other = ExpectationSuite(**other_dict)
                except ValidationError:
                    logger.debug(
                        "Unable to evaluate equivalence of ExpectationConfiguration object with dict because "  # noqa: E501
                        "dict other could not be instantiated as an ExpectationConfiguration"
                    )
                    return NotImplemented
            else:
                # Delegate comparison to the other instance
                return NotImplemented

        exp_count_is_equal = len(self.expectations) == len(other.expectations)

        exp_configs_are_equal = all(
            mine.isEquivalentTo(theirs)
            for (mine, theirs) in zip(
                self.expectation_configurations, other.expectation_configurations
            )
        )

        return exp_count_is_equal and exp_configs_are_equal

    def __eq__(self, other):
        """ExpectationSuite equality ignores instance identity, relying only on properties."""
        if not isinstance(other, self.__class__):
            # Delegate comparison to the other instance's __eq__.
            return NotImplemented
        return all(
            (
                self.name == other.name,
                self.expectations == other.expectations,
                self.evaluation_parameters == other.evaluation_parameters,
                self.meta == other.meta,
            )
        )

    def __ne__(self, other):
        # By using the == operator, the returned NotImplemented is handled correctly.
        return not self == other

    def __repr__(self):
        return json.dumps(self.to_json_dict(), indent=2)

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2)

    def __deepcopy__(self, memo: dict):
        cls = self.__class__
        result = cls.__new__(cls)

        memo[id(self)] = result

        attributes_to_copy = set(ExpectationSuiteSchema().fields.keys())
        for key in attributes_to_copy:
            setattr(result, key, deepcopy(getattr(self, key), memo))

        return result

    @public_api
    @override
    def to_json_dict(self) -> Dict[str, JSONValues]:
        """Returns a JSON-serializable dict representation of this ExpectationSuite.

        Returns:
            A JSON-serializable dict representation of this ExpectationSuite.
        """
        myself = expectationSuiteSchema.dump(self)
        # NOTE - JPC - 20191031: migrate to expectation-specific schemas that subclass result with properly-typed  # noqa: E501
        # schemas to get serialization all-the-way down via dump
        expectation_configurations = [exp.configuration for exp in self.expectations]
        myself["expectations"] = convert_to_json_serializable(expectation_configurations)
        try:
            myself["evaluation_parameters"] = convert_to_json_serializable(
                myself["evaluation_parameters"]
            )
        except KeyError:
            pass  # Allow evaluation parameters to be missing if empty
        myself["meta"] = convert_to_json_serializable(myself["meta"])
        return myself

    def get_evaluation_parameter_dependencies(self) -> dict:
        dependencies: dict = {}
        for expectation in self.expectations:
            t = expectation.configuration.get_evaluation_parameter_dependencies()
            nested_update(dependencies, t)

        dependencies = _deduplicate_evaluation_parameter_dependencies(dependencies)
        return dependencies

    def get_citations(
        self,
        sort: bool = True,
        require_batch_kwargs: bool = False,
        require_batch_request: bool = False,
        require_profiler_config: bool = False,
    ) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = self.meta.get("citations", [])
        if require_batch_kwargs:
            citations = self._filter_citations(citations=citations, filter_key="batch_kwargs")
        if require_batch_request:
            citations = self._filter_citations(citations=citations, filter_key="batch_request")
        if require_profiler_config:
            citations = self._filter_citations(citations=citations, filter_key="profiler_config")
        if not sort:
            return citations
        return self._sort_citations(citations=citations)

    @staticmethod
    def _filter_citations(citations: List[Dict[str, Any]], filter_key) -> List[Dict[str, Any]]:
        citations_with_bk: List[Dict[str, Any]] = []
        for citation in citations:
            if filter_key in citation and citation.get(filter_key):
                citations_with_bk.append(citation)

        return citations_with_bk

    @staticmethod
    def _sort_citations(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(citations, key=lambda x: x["citation_date"])

    @public_api
    def remove_expectation(
        self,
        expectation_configuration: Optional[ExpectationConfiguration] = None,
        match_type: str = "domain",
        remove_multiple_matches: bool = False,
        id: Optional[Union[str, uuid.UUID]] = None,
    ) -> List[ExpectationConfiguration]:
        """Remove an ExpectationConfiguration from the ExpectationSuite.

        Args:
            expectation_configuration: A potentially incomplete (partial) Expectation Configuration to match against.
            match_type: This determines what kwargs to use when matching. Options are 'domain' to match based
                on the data evaluated by that expectation, 'success' to match based on all configuration parameters
                that influence whether an expectation succeeds based on a given batch of data, and 'runtime' to match
                based on all configuration parameters.
            remove_multiple_matches: If True, will remove multiple matching expectations.
            id: Great Expectations Cloud id for an Expectation.

        Returns:
            The list of deleted ExpectationConfigurations.

        Raises:
            TypeError: Must provide either expectation_configuration or id.
            ValueError: No match or multiple matches found (and remove_multiple_matches=False).
        """  # noqa: E501
        expectation_configurations = [exp.configuration for exp in self.expectations]
        if expectation_configuration is None and id is None:
            raise TypeError("Must provide either expectation_configuration or id")  # noqa: TRY003

        found_expectation_indexes = self.find_expectation_indexes(
            expectation_configuration=expectation_configuration,
            match_type=match_type,
            id=id,  # type: ignore[arg-type]
        )
        if len(found_expectation_indexes) < 1:
            raise ValueError("No matching expectation was found.")  # noqa: TRY003

        elif len(found_expectation_indexes) > 1:
            if remove_multiple_matches:
                removed_expectations = []
                for index in sorted(found_expectation_indexes, reverse=True):
                    removed_expectations.append(expectation_configurations.pop(index))
                self.expectations = [
                    self._build_expectation(config) for config in expectation_configurations
                ]
                return removed_expectations
            else:
                raise ValueError(  # noqa: TRY003
                    "More than one matching expectation was found. Specify more precise matching criteria,"  # noqa: E501
                    "or set remove_multiple_matches=True"
                )

        else:
            result = [expectation_configurations.pop(found_expectation_indexes[0])]
            self.expectations = [
                self._build_expectation(config) for config in expectation_configurations
            ]
            return result

    def remove_all_expectations_of_type(
        self, expectation_types: Union[List[str], str]
    ) -> List[ExpectationConfiguration]:
        if isinstance(expectation_types, str):
            expectation_types = [expectation_types]

        removed_expectations = [
            expectation.configuration
            for expectation in self.expectations
            if expectation.expectation_type in expectation_types
        ]
        self.expectations = [
            expectation
            for expectation in self.expectations
            if expectation.expectation_type not in expectation_types
        ]

        return removed_expectations

    def find_expectation_indexes(
        self,
        expectation_configuration: Optional[ExpectationConfiguration] = None,
        match_type: str = "domain",
        id: Optional[str] = None,
    ) -> List[int]:
        """
        Find indexes of Expectations matching the given ExpectationConfiguration on the given match_type.
        If a id is provided, match_type is ignored and only indexes of Expectations
        with matching id are returned.

        Args:
            expectation_configuration: A potentially incomplete (partial) Expectation Configuration to match against to
                find the index of any matching Expectation Configurations on the suite.
            match_type: This determines what kwargs to use when matching. Options are 'domain' to match based
                on the data evaluated by that expectation, 'success' to match based on all configuration parameters
                 that influence whether an expectation succeeds based on a given batch of data, and 'runtime' to match
                 based on all configuration parameters
            id: Great Expectations Cloud id

        Returns: A list of indexes of matching ExpectationConfiguration

        Raises:
            InvalidExpectationConfigurationError

        """  # noqa: E501
        from great_expectations.expectations.expectation_configuration import (
            ExpectationConfiguration,
        )

        if expectation_configuration is None and id is None:
            raise TypeError("Must provide either expectation_configuration or id")  # noqa: TRY003

        if expectation_configuration and not isinstance(
            expectation_configuration, ExpectationConfiguration
        ):
            raise gx_exceptions.InvalidExpectationConfigurationError(  # noqa: TRY003
                "Ensure that expectation configuration is valid."
            )

        match_indexes = []
        for idx, expectation in enumerate(self.expectations):
            if id is not None:
                if expectation.id == id:
                    match_indexes.append(idx)
            else:  # noqa: PLR5501
                if expectation.configuration.isEquivalentTo(
                    other=expectation_configuration,  # type: ignore[arg-type]
                    match_type=match_type,
                ):
                    match_indexes.append(idx)

        return match_indexes

    @public_api
    def find_expectations(
        self,
        expectation_configuration: Optional[ExpectationConfiguration] = None,
        match_type: str = "domain",
        id: Optional[str] = None,
    ) -> List[ExpectationConfiguration]:
        """
        Find Expectations matching the given ExpectationConfiguration on the given match_type.
        If a id is provided, match_type is ignored and only Expectations with matching
        id are returned.

        Args:
            expectation_configuration: A potentially incomplete (partial) Expectation Configuration to match against to
                find the index of any matching Expectation Configurations on the suite.
            match_type: This determines what kwargs to use when matching. Options are 'domain' to match based
                on the data evaluated by that expectation, 'success' to match based on all configuration parameters
                 that influence whether an expectation succeeds based on a given batch of data, and 'runtime' to match
                 based on all configuration parameters
            id: Great Expectations Cloud id

        Returns: A list of matching ExpectationConfigurations
        """  # noqa: E501

        if expectation_configuration is None and id is None:
            raise TypeError("Must provide either expectation_configuration or id")  # noqa: TRY003

        found_expectation_indexes: List[int] = self.find_expectation_indexes(
            expectation_configuration, match_type, id
        )

        if len(found_expectation_indexes) > 0:
            return [self.expectations[idx].configuration for idx in found_expectation_indexes]

        return []

    def _add_expectation(
        self,
        expectation_configuration: ExpectationConfiguration,
        match_type: str = "domain",
        overwrite_existing: bool = True,
    ) -> ExpectationConfiguration:
        """
        If successful, upserts ExpectationConfiguration into this ExpectationSuite.

        Args:
            expectation_configuration: The ExpectationConfiguration to add or update
            match_type: The criteria used to determine whether the Suite already has an ExpectationConfiguration
                and so whether we should add or replace.
            overwrite_existing: If the expectation already exists, this will overwrite if True and raise an error if
                False.

        Returns:
            The ExpectationConfiguration to add or replace.

        Raises:
            More than one match
            One match if overwrite_existing = False
        """  # noqa: E501

        found_expectation_indexes = self.find_expectation_indexes(
            expectation_configuration, match_type
        )

        if len(found_expectation_indexes) > 1:
            raise ValueError(  # noqa: TRY003
                "More than one matching expectation was found. Please be more specific with your search "  # noqa: E501
                "criteria"
            )
        elif len(found_expectation_indexes) == 1:
            # Currently, we completely replace the expectation_configuration, but we could potentially use patch_expectation  # noqa: E501
            # to update instead. We need to consider how to handle meta in that situation.
            # patch_expectation = jsonpatch.make_patch(self.expectations[found_expectation_index] \
            #   .kwargs, expectation_configuration.kwargs)
            # patch_expectation.apply(self.expectations[found_expectation_index].kwargs, in_place=True)  # noqa: E501
            if overwrite_existing:
                # if existing Expectation has a id, add it back to the new Expectation Configuration
                existing_expectation_id = self.expectations[found_expectation_indexes[0]].id
                if existing_expectation_id is not None:
                    expectation_configuration.id = existing_expectation_id

                self.expectations[found_expectation_indexes[0]] = self._build_expectation(
                    expectation_configuration=expectation_configuration
                )
            else:
                raise gx_exceptions.DataContextError(  # noqa: TRY003
                    "A matching ExpectationConfiguration already exists. If you would like to overwrite this "  # noqa: E501
                    "ExpectationConfiguration, set overwrite_existing=True"
                )
        else:
            self.expectations.append(
                self._build_expectation(expectation_configuration=expectation_configuration)
            )

        return expectation_configuration

    def add_expectation_configurations(
        self,
        expectation_configurations: List[ExpectationConfiguration],
        match_type: str = "domain",
        overwrite_existing: bool = True,
    ) -> List[ExpectationConfiguration]:
        """Upsert a list of ExpectationConfigurations into this ExpectationSuite.

        Args:
            expectation_configurations: The List of candidate new/modifed "ExpectationConfiguration" objects for Suite.
            match_type: The criteria used to determine whether the Suite already has an "ExpectationConfiguration"
                object, matching the specified criteria, and thus whether we should add or replace (i.e., "upsert").
            overwrite_existing: If "ExpectationConfiguration" already exists, this will cause it to be overwritten if
                True and raise an error if False.

        Returns:
            The List of "ExpectationConfiguration" objects attempted to be added or replaced (can differ from the list
            of "ExpectationConfiguration" objects in "self.expectations" at the completion of this method's execution).

        Raises:
            More than one match
            One match if overwrite_existing = False
        """  # noqa: E501
        expectation_configuration: ExpectationConfiguration
        expectation_configurations_attempted_to_be_added: List[ExpectationConfiguration] = [
            self.add_expectation_configuration(
                expectation_configuration=expectation_configuration,
                match_type=match_type,
                overwrite_existing=overwrite_existing,
            )
            for expectation_configuration in expectation_configurations
        ]
        return expectation_configurations_attempted_to_be_added

    @public_api
    def add_expectation_configuration(
        self,
        expectation_configuration: ExpectationConfiguration,
        match_type: str = "domain",
        overwrite_existing: bool = True,
    ) -> ExpectationConfiguration:
        """Upsert specified ExpectationConfiguration into this ExpectationSuite.

        Args:
            expectation_configuration: The ExpectationConfiguration to add or update.
            match_type: The criteria used to determine whether the Suite already has an ExpectationConfiguration
                and so whether we should add or replace.
            overwrite_existing: If the expectation already exists, this will overwrite if True and raise an error if
                False.

        Returns:
            The ExpectationConfiguration to add or replace.

        Raises:
            ValueError: More than one match
            DataContextError: One match if overwrite_existing = False

        # noqa: DAR402
        """  # noqa: E501
        self._build_expectation(expectation_configuration)
        return self._add_expectation(
            expectation_configuration=expectation_configuration,
            match_type=match_type,
            overwrite_existing=overwrite_existing,
        )

    def _build_expectation(
        self, expectation_configuration: ExpectationConfiguration
    ) -> Expectation:
        try:
            expectation = expectation_configuration.to_domain_obj()
            expectation.register_save_callback(save_callback=self._save_expectation)
            return expectation
        except (
            gx_exceptions.ExpectationNotFoundError,
            gx_exceptions.InvalidExpectationConfigurationError,
        ) as e:
            raise gx_exceptions.InvalidExpectationConfigurationError(  # noqa: TRY003
                f"Could not add expectation; provided configuration is not valid: {e.message}"
            ) from e

    @public_api
    def show_expectations_by_domain_type(self) -> None:
        """Displays "ExpectationConfiguration" list, grouped by "domain_type", in predetermined designated order.

        The means of displaying is through the use of the "Pretty Print" library method "pprint.pprint()".
        """  # noqa: E501
        expectation_configurations_by_domain: Dict[str, List[ExpectationConfiguration]] = (
            self.get_grouped_and_ordered_expectations_by_domain_type()
        )

        domain_type: str
        expectation_configurations: List[ExpectationConfiguration]
        for (
            domain_type,
            expectation_configurations,
        ) in expectation_configurations_by_domain.items():
            pprint.pprint(object=MetricDomainTypes(domain_type).value.capitalize())
            self.show_expectations_by_expectation_type(
                expectation_configurations=expectation_configurations
            )

    def show_expectations_by_expectation_type(
        self,
        expectation_configurations: Optional[List[ExpectationConfiguration]] = None,
    ) -> None:
        """Displays "ExpectationConfiguration" list, grouped by "expectation_type", in predetermined designated order.

        The means of displaying is through the use of the "Pretty Print" library method "pprint.pprint()".
        """  # noqa: E501
        if expectation_configurations is None:
            expectation_configurations = (
                self.get_grouped_and_ordered_expectations_by_expectation_type()
            )

        expectation_configuration: ExpectationConfiguration
        domain_type: MetricDomainTypes
        kwargs: dict
        pprint_objects: List[dict] = []
        for expectation_configuration in expectation_configurations:
            domain_type = expectation_configuration.get_domain_type()
            kwargs = expectation_configuration.kwargs
            pprint_objects.append(
                {
                    expectation_configuration.expectation_type: {
                        "domain": domain_type.value,
                        **kwargs,
                    }
                }
            )
        pprint.pprint(
            object=pprint_objects,
            indent=2,
        )

    def get_grouped_and_ordered_expectations_by_domain_type(
        self,
    ) -> Dict[str, List[ExpectationConfiguration]]:
        """
        Returns "ExpectationConfiguration" list in predetermined order by passing appropriate methods for retrieving
        "ExpectationConfiguration" lists by corresponding "domain_type" (with "table" first; then "column", and so on).
        """  # noqa: E501
        expectation_configurations_by_domain: Dict[str, List[ExpectationConfiguration]] = (
            self._get_expectations_by_domain_using_accessor_method(
                domain_type=MetricDomainTypes.TABLE.value,
                accessor_method=self.get_table_expectations,
            )
        )
        expectation_configurations_by_domain.update(
            self._get_expectations_by_domain_using_accessor_method(
                domain_type=MetricDomainTypes.COLUMN.value,
                accessor_method=self.get_column_expectations,
            )
        )
        expectation_configurations_by_domain.update(
            self._get_expectations_by_domain_using_accessor_method(
                domain_type=MetricDomainTypes.COLUMN_PAIR.value,
                accessor_method=self.get_column_pair_expectations,
            )
        )
        expectation_configurations_by_domain.update(
            self._get_expectations_by_domain_using_accessor_method(
                domain_type=MetricDomainTypes.MULTICOLUMN.value,
                accessor_method=self.get_multicolumn_expectations,
            )
        )
        return expectation_configurations_by_domain

    def get_grouped_and_ordered_expectations_by_expectation_type(
        self,
    ) -> List[ExpectationConfiguration]:
        """
        Returns "ExpectationConfiguration" list, grouped by "expectation_type", in predetermined designated order.
        """  # noqa: E501
        table_expectation_configurations: List[ExpectationConfiguration] = sorted(
            self.get_table_expectations(),
            key=lambda element: element["expectation_type"],
        )
        column_expectation_configurations: List[ExpectationConfiguration] = sorted(
            self.get_column_expectations(),
            key=lambda element: element["expectation_type"],
        )
        column_pair_expectation_configurations: List[ExpectationConfiguration] = sorted(
            self.get_column_pair_expectations(),
            key=lambda element: element["expectation_type"],
        )
        multicolumn_expectation_configurations: List[ExpectationConfiguration] = sorted(
            self.get_multicolumn_expectations(),
            key=lambda element: element["expectation_type"],
        )
        return (
            table_expectation_configurations
            + column_expectation_configurations
            + column_pair_expectation_configurations
            + multicolumn_expectation_configurations
        )

    def get_table_expectations(self) -> List[ExpectationConfiguration]:
        """Return a list of table expectations."""
        expectation_configurations: List[ExpectationConfiguration] = [
            exp.configuration for exp in self.expectations
        ]
        expectation_configurations = list(
            filter(
                lambda element: element.get_domain_type() == MetricDomainTypes.TABLE,
                expectation_configurations,
            )
        )

        expectation_configuration: ExpectationConfiguration
        for expectation_configuration in expectation_configurations:
            expectation_configuration.kwargs = deep_filter_properties_iterable(
                properties=expectation_configuration.kwargs, clean_falsy=True
            )

        return expectation_configurations

    def get_column_expectations(self) -> List[ExpectationConfiguration]:
        """Return a list of column map expectations."""
        expectation_configurations: List[ExpectationConfiguration] = [
            exp.configuration for exp in self.expectations
        ]
        expectation_configurations = list(
            filter(
                lambda element: element.get_domain_type() == MetricDomainTypes.COLUMN,
                expectation_configurations,
            )
        )

        expectation_configuration: ExpectationConfiguration
        kwargs: dict
        column_name: str
        for expectation_configuration in expectation_configurations:
            kwargs = deep_filter_properties_iterable(
                properties=expectation_configuration.kwargs, clean_falsy=True
            )
            column_name = kwargs.pop("column")
            expectation_configuration.kwargs = {"column": column_name, **kwargs}

        return expectation_configurations

    # noinspection PyPep8Naming
    def get_column_pair_expectations(self) -> List[ExpectationConfiguration]:
        """Return a list of column_pair map expectations."""
        expectation_configurations: List[ExpectationConfiguration] = [
            exp.configuration for exp in self.expectations
        ]

        expectation_configurations = list(
            filter(
                lambda element: element.get_domain_type() == MetricDomainTypes.COLUMN_PAIR,
                expectation_configurations,
            )
        )

        expectation_configuration: ExpectationConfiguration
        kwargs: dict
        column_A_name: str
        column_B_name: str
        for expectation_configuration in expectation_configurations:
            kwargs = deep_filter_properties_iterable(
                properties=expectation_configuration.kwargs, clean_falsy=True
            )
            column_A_name = kwargs.pop("column_A")
            column_B_name = kwargs.pop("column_B")
            expectation_configuration.kwargs = {
                "column_A": column_A_name,
                "column_B": column_B_name,
                **kwargs,
            }

        return expectation_configurations

    def get_multicolumn_expectations(self) -> List[ExpectationConfiguration]:
        """Return a list of multicolumn map expectations."""
        expectation_configurations: List[ExpectationConfiguration] = [
            exp.configuration for exp in self.expectations
        ]

        expectation_configurations = list(
            filter(
                lambda element: element.get_domain_type() == MetricDomainTypes.MULTICOLUMN,
                expectation_configurations,
            )
        )

        expectation_configuration: ExpectationConfiguration
        kwargs: dict
        column_list: str
        for expectation_configuration in expectation_configurations:
            kwargs = deep_filter_properties_iterable(
                properties=expectation_configuration.kwargs, clean_falsy=True
            )
            column_list = kwargs.pop("column_list")
            expectation_configuration.kwargs = {"column_list": column_list, **kwargs}

        return expectation_configurations

    def get_grouped_and_ordered_expectations_by_column(
        self, expectation_type_filter: Optional[str] = None
    ) -> Tuple[Dict[str, List[ExpectationConfiguration]], List[str]]:
        expectations_by_column: Dict[str, List[ExpectationConfiguration]] = {}
        ordered_columns: List[str] = []

        column: str
        expectation: ExpectationConfiguration
        expectation_configurations = [exp.configuration for exp in self.expectations]
        for expectation in expectation_configurations:
            if "column" in expectation.kwargs:
                column = expectation.kwargs["column"]
            else:
                column = "_nocolumn"

            if column not in expectations_by_column:
                expectations_by_column[column] = []

            if (
                expectation_type_filter is None
                or expectation.expectation_type == expectation_type_filter
            ):
                expectations_by_column[column].append(expectation)

            # if possible, get the order of columns from expect_table_columns_to_match_ordered_list
            if (
                expectation.expectation_type == "expect_table_columns_to_match_ordered_list"
                and expectation.kwargs.get("column_list")
            ):
                exp_column_list: List[str] = expectation.kwargs["column_list"]
                if exp_column_list and len(exp_column_list) > 0:
                    ordered_columns = exp_column_list

        # Group items by column
        sorted_columns = sorted(list(expectations_by_column.keys()))

        # only return ordered columns from expect_table_columns_to_match_ordered_list evr if they match set of column  # noqa: E501
        # names from entire evr, else use alphabetic sort
        if set(sorted_columns) == set(ordered_columns):
            return expectations_by_column, ordered_columns

        return expectations_by_column, sorted_columns

    @staticmethod
    def _get_expectations_by_domain_using_accessor_method(
        domain_type: str, accessor_method: Callable
    ) -> Dict[str, List[ExpectationConfiguration]]:
        expectation_configurations_by_domain: Dict[str, List[ExpectationConfiguration]] = {}

        expectation_configurations: List[ExpectationConfiguration]
        expectation_configuration: ExpectationConfiguration
        for expectation_configuration in accessor_method():
            expectation_configurations = expectation_configurations_by_domain.get(  # type: ignore[assignment]
                domain_type
            )
            if expectation_configurations is None:
                expectation_configurations = []
                expectation_configurations_by_domain[domain_type] = expectation_configurations

            expectation_configurations.append(expectation_configuration)

        return expectation_configurations_by_domain

    def render(self) -> None:
        """
        Renders content using the atomic prescriptive renderer for each expectation configuration associated with
           this ExpectationSuite to ExpectationConfiguration.rendered_content.
        """  # noqa: E501
        from great_expectations.render.renderer.inline_renderer import InlineRenderer

        for expectation in self.expectations:
            inline_renderer = InlineRenderer(render_object=expectation.configuration)

            rendered_content: List[RenderedAtomicContent] = inline_renderer.get_rendered_content()

            expectation.rendered_content = (
                inline_renderer.replace_or_keep_existing_rendered_content(
                    existing_rendered_content=expectation.rendered_content,
                    new_rendered_content=rendered_content,
                    failed_renderer_type=AtomicPrescriptiveRendererType.FAILED,
                )
            )

    def identifier_bundle(self) -> _IdentifierBundle:
        # Utilized as a custom json_encoder
        from great_expectations import project_manager

        if not self.id:
            expectation_store = project_manager.get_expectations_store()
            key = expectation_store.get_key(name=self.name, id=None)
            expectation_store.add(key=key, value=self)

        return _IdentifierBundle(name=self.name, id=self.id)


_TExpectationSuite = TypeVar("_TExpectationSuite", ExpectationSuite, dict)


class ExpectationSuiteSchema(Schema):
    name = fields.Str()
    id = fields.UUID(required=False, allow_none=True)
    expectations = fields.List(fields.Nested("ExpectationConfigurationSchema"))
    evaluation_parameters = fields.Dict(allow_none=True)
    meta = fields.Dict()
    notes = fields.Raw(required=False, allow_none=True)

    # NOTE: 20191107 - JPC - we may want to remove clean_empty and update tests to require the other fields;  # noqa: E501
    # doing so could also allow us not to have to make a copy of data in the pre_dump method.
    # noinspection PyMethodMayBeStatic
    def clean_empty(self, data: _TExpectationSuite) -> _TExpectationSuite:
        if isinstance(data, ExpectationSuite):
            # We are hitting this TypeVar narrowing mypy bug: https://github.com/python/mypy/issues/10817
            data = self._clean_empty_suite(data)  # type: ignore[assignment]
        elif isinstance(data, dict):
            data = self._clean_empty_dict(data)
        return data

    @staticmethod
    def _clean_empty_suite(data: ExpectationSuite) -> ExpectationSuite:
        if not hasattr(data, "evaluation_parameters"):
            pass
        elif len(data.evaluation_parameters) == 0:
            del data.evaluation_parameters

        if not hasattr(data, "meta"):
            pass
        elif data.meta is None or data.meta == []:
            pass
        elif len(data.meta) == 0:
            del data.meta
        return data

    @staticmethod
    def _clean_empty_dict(data: dict) -> dict:
        if "evaluation_parameters" in data and len(data["evaluation_parameters"]) == 0:
            data.pop("evaluation_parameters")
        if "meta" in data and len(data["meta"]) == 0:
            data.pop("meta")
        if "notes" in data and not data.get("notes"):
            data.pop("notes")
        return data

    # noinspection PyUnusedLocal
    @pre_dump
    def prepare_dump(self, data, **kwargs):
        data = deepcopy(data)
        for key in data:
            if key.startswith("_"):
                continue
            data[key] = convert_to_json_serializable(data[key])

        data = self.clean_empty(data)
        return data

    @post_dump(pass_original=True)
    def insert_expectations(self, data, original_data, **kwargs) -> dict:
        if isinstance(original_data, dict):
            expectations = original_data.get("expectations", [])
        else:
            expectations = original_data.expectation_configurations
        data["expectations"] = convert_to_json_serializable(expectations)
        return data

    @post_load
    def _convert_uuids_to_str(self, data, **kwargs):
        """
        Utilize UUID for data validation but convert to string before usage in business logic
        """
        attr = "id"
        uuid_val = data.get(attr)
        if uuid_val:
            data[attr] = str(uuid_val)
        return data


expectationSuiteSchema: ExpectationSuiteSchema = ExpectationSuiteSchema()
