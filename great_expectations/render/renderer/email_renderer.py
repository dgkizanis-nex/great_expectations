from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from great_expectations.core.id_dict import BatchKwargs
from great_expectations.render.renderer.renderer import Renderer

if TYPE_CHECKING:
    from great_expectations.checkpoint.v1_checkpoint import CheckpointResult
    from great_expectations.core.expectation_validation_result import (
        ExpectationSuiteValidationResult,
    )


class EmailRenderer(Renderer):
    def v1_render(self, checkpoint_result: CheckpointResult) -> tuple[str, str]:
        checkpoint_name = checkpoint_result.checkpoint_config.name
        status = checkpoint_result.success
        title = f"{checkpoint_name}: {status}"

        text_blocks: list[str] = []
        for result in checkpoint_result.run_results.values():
            html = self._render_validation_result(result=result)
            text_blocks.append(html)

        return title, self._concatenate_blocks(text_blocks=text_blocks)

    def _render_validation_result(self, result: ExpectationSuiteValidationResult) -> str:
        suite_name = result.suite_name
        asset_name = result.asset_name or "__no_asset_name__"
        n_checks_succeeded = result.statistics["successful_expectations"]
        n_checks = result.statistics["evaluated_expectations"]
        run_id = result.meta.get("run_id", "__no_run_id__")
        batch_id = result.batch_id
        check_details_text = f"<strong>{n_checks_succeeded}</strong> of <strong>{n_checks}</strong> expectations were met"  # noqa: E501
        status = "Success 🎉" if result.success else "Failed ❌"

        title = f"<h3><u>{suite_name}</u></h3>"
        html = textwrap.dedent(
            f"""\
            <p><strong>{title}</strong></p>
            <p><strong>Batch Validation Status</strong>: {status}</p>
            <p><strong>Expectation Suite Name</strong>: {suite_name}</p>
            <p><strong>Data Asset Name</strong>: {asset_name}</p>
            <p><strong>Run ID</strong>: {run_id}</p>
            <p><strong>Batch ID</strong>: {batch_id}</p>
            <p><strong>Summary</strong>: {check_details_text}</p>"""
        )

        return html

    def _concatenate_blocks(self, text_blocks: list[str]) -> str:
        return "<br>".join(text_blocks)

    def render(  # noqa: C901, PLR0912
        self, validation_result=None, data_docs_pages=None, notify_with=None
    ):
        default_text = "No validation occurred. Please ensure you passed a validation_result."
        status = "Failed ❌"

        title = default_text

        html = default_text

        if validation_result:
            expectation_suite_name = validation_result.meta.get(
                "expectation_suite_name", "__no_expectation_suite_name__"
            )

            if "batch_kwargs" in validation_result.meta:
                data_asset_name = validation_result.meta["batch_kwargs"].get(
                    "data_asset_name", "__no_data_asset_name__"
                )
            elif "active_batch_definition" in validation_result.meta:
                data_asset_name = (
                    validation_result.meta["active_batch_definition"].data_asset_name
                    if validation_result.meta["active_batch_definition"].data_asset_name
                    else "__no_data_asset_name__"
                )
            else:
                data_asset_name = "__no_data_asset_name__"

            n_checks_succeeded = validation_result.statistics["successful_expectations"]
            n_checks = validation_result.statistics["evaluated_expectations"]
            run_id = validation_result.meta.get("run_id", "__no_run_id__")
            batch_id = BatchKwargs(validation_result.meta.get("batch_kwargs", {})).to_id()
            check_details_text = f"<strong>{n_checks_succeeded}</strong> of <strong>{n_checks}</strong> expectations were met"  # noqa: E501

            if validation_result.success:
                status = "Success 🎉"

            title = f"{expectation_suite_name}: {status}"

            html = textwrap.dedent(
                f"""\
                <p><strong>Batch Validation Status</strong>: {status}</p>
                <p><strong>Expectation suite name</strong>: {expectation_suite_name}</p>
                <p><strong>Data asset name</strong>: {data_asset_name}</p>
                <p><strong>Run ID</strong>: {run_id}</p>
                <p><strong>Batch ID</strong>: {batch_id}</p>
                <p><strong>Summary</strong>: {check_details_text}</p>"""
            )
            if data_docs_pages:
                if notify_with is not None:
                    for docs_link_key in notify_with:
                        if docs_link_key in data_docs_pages.keys():
                            docs_link = data_docs_pages[docs_link_key]
                            report_element = self._get_report_element(docs_link)
                        else:
                            report_element = str(
                                f"<strong>ERROR</strong>: The email is trying to provide a link to the following DataDocs: "  # noqa: E501
                                f"`{docs_link_key!s}`, but it is not configured under data_docs_sites "  # noqa: E501
                                "in the great_expectations.yml</br>"
                            )
                            logger.critical(report_element)
                        if report_element:
                            print(report_element)
                            html += report_element
                else:
                    for docs_link_key in data_docs_pages.keys():
                        if docs_link_key == "class":
                            continue
                        docs_link = data_docs_pages[docs_link_key]
                        report_element = self._get_report_element(docs_link)
                        if report_element:
                            html += report_element

            if "result_reference" in validation_result.meta:
                result_reference = validation_result.meta["result_reference"]
                report_element = f"- <strong>Validation Report</strong>: {result_reference}</br>"
                html += report_element

            if "dataset_reference" in validation_result.meta:
                dataset_reference = validation_result.meta["dataset_reference"]
                report_element = (
                    f"- <strong>Validation data asset</strong>: {dataset_reference}</br>"
                )
                html += report_element

        documentation_url = "https://docs.greatexpectations.io/docs/terms/data_docs"
        footer_section = f'<p>Learn <a href="{documentation_url}">here</a> how to review validation results in Data Docs</p>'  # noqa: E501
        html += footer_section
        return title, html

    def _get_report_element(self, docs_link):
        report_element = None
        if docs_link:
            try:
                if "file://" in docs_link:
                    # handle special case since the email does not render these links
                    report_element = str(
                        f'<p><strong>DataDocs</strong> can be found here: <a href="{docs_link}">{docs_link}</a>.</br>'  # noqa: E501
                        "(Please copy and paste link into a browser to view)</p>",
                    )
                else:
                    report_element = f'<p><strong>DataDocs</strong> can be found here: <a href="{docs_link}">{docs_link}</a>.</p>'  # noqa: E501
            except Exception as e:
                logger.warning(
                    f"""EmailRenderer had a problem with generating the docs link.
                    link used to generate the docs link is: {docs_link} and is of type: {type(docs_link)}.
                    Error: {e}"""  # noqa: E501
                )
                return
        else:
            logger.warning("No docs link found. Skipping data docs link in the email message.")
        return report_element
