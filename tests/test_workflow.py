import os
from datetime import timedelta
from typing import cast

import pytest
from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from zucker import AioClient, RequestsClient, model
from zucker.client import AsyncClient, SyncClient


def get_credentials() -> tuple[str, str, str, str]:
    if "ZUCKER_TEST_CREDENTIALS" not in os.environ:
        pytest.skip("test server credentials not configured")

    credentials = tuple(os.environ["ZUCKER_TEST_CREDENTIALS"].split("|"))
    assert len(credentials) == 4, "invalid format for test server credentials"
    return cast("tuple[str, str, str, str]", credentials)


@pytest.fixture(scope="module")
def live_sync_client() -> SyncClient:
    credentials = get_credentials()
    return RequestsClient(
        base_url=credentials[0],
        username=credentials[1],
        password=credentials[2],
        client_platform=credentials[3],
        verify_ssl=False,
    )


@pytest.fixture(scope="module")
def live_async_client() -> AsyncClient:
    credentials = get_credentials()
    return AioClient(
        base_url=credentials[0],
        username=credentials[1],
        password=credentials[2],
        client_platform=credentials[3],
        verify_ssl=False,
    )


@st.composite
def names(draw: st.DrawFn, min_size: int = 4, max_size: int = 100) -> str:
    return draw(
        st.text(
            st.characters(whitelist_categories=("L",)),
            min_size=min_size,
            max_size=max_size,
        )
    )


class BaseLead(model.UnboundModule):
    first_name = model.StringField()
    last_name = model.StringField()
    description = model.StringField()


@settings(
    max_examples=5,
    phases=(Phase.explicit, Phase.generate, Phase.target),
    deadline=timedelta(seconds=10),
)
@given(names(), names(), st.text(min_size=10))
def test_crud(
    live_sync_client: SyncClient, first_name: str, last_name: str, description: str
) -> None:
    """This test runs a complete workflow for working with records.

    The following steps will be performed on a live Sugar instance:
    - Create a record
    - Read back the newly created record's data
    - Perform some updates
    - Delete the record again

    In order for this test to work, credentials to the Sugar server must be provided via
    the ``ZUCKER_TEST_CREDENTIALS`` environment variable. It should have a value of the
    form ``BASE_URL|USERNAME|PASSWORD|CLIENT_PLATFORM``. SSL verification will be
    disabled for this test. If the environment variable is not present, the test is
    skipped all together.
    """

    class Lead(model.SyncModule, BaseLead, client=live_sync_client, api_name="Leads"):
        pass

    lead_1 = Lead(first_name=first_name, last_name=last_name)
    lead_1.save()
    lead_id = lead_1.id

    # Clear the record cache because we want actually new items.
    Lead._record_cache.clear()

    view = Lead.find(Lead.id == lead_id)
    assert len(view) == 1
    lead_2 = view[0]
    # Make sure we are not using the record cache.
    assert lead_1 is not lead_2

    assert lead_2.id == lead_1.id
    assert lead_2.first_name == first_name
    assert lead_2.last_name == last_name

    lead_2.description = description
    lead_2.save()
    lead_1.refresh()
    assert lead_1.description == description

    lead_1.delete()
    assert len(Lead.find(Lead.id == lead_id)) == 0


async def test_bulk(live_async_client: AsyncClient) -> None:
    crm = live_async_client

    class Lead(model.AsyncModule, BaseLead, client=crm, api_name="Leads"):
        pass

    lead_a: Lead
    lead_b: Lead
    lead_c: Lead

    lead_a, lead_b, lead_c = await crm.bulk(
        Lead.find()[0],
        Lead.find()[1],
        Lead.find()[-1],
    )

    assert isinstance(lead_a, Lead)
    assert isinstance(lead_b, Lead)
    assert isinstance(lead_c, Lead)
    assert lead_a.id != lead_b.id and lead_b.id != lead_c.id and lead_c.id != lead_a.id
