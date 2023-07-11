from utils import Ping
from contextlib import AsyncExitStack
from mesh_api import API
from utils import (
    ConnectionTag,
    new_connection_with_conn_tracker,
    testing,
)
from telio_features import TelioFeatures, Direct
from utils.connection_tracker import (
    generate_connection_tracker_config,
    ConnectionLimits,
)
import asyncio
import pytest
import telio

STUN_PROVIDER = ["stun"]

DOCKER_CONE_GW_2_IP = "10.0.254.2"

UHP_conn_client_types = [
    (
        STUN_PROVIDER,
        ConnectionTag.DOCKER_CONE_CLIENT_1,
        ConnectionTag.DOCKER_CONE_CLIENT_2,
        DOCKER_CONE_GW_2_IP,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint_providers, client1_type, client2_type, reflexive_ip",
    UHP_conn_client_types,
)
async def test_connect_different_telio_version_through_relay(
    endpoint_providers,
    client1_type,
    client2_type,
    reflexive_ip,
) -> None:
    async with AsyncExitStack() as exit_stack:
        api = API()

        (alpha, beta, gamma) = api.default_config_three_nodes()

        (alpha_conn, alpha_conn_tracker,) = await exit_stack.enter_async_context(
            new_connection_with_conn_tracker(
                client1_type,
                generate_connection_tracker_config(
                    client1_type,
                    derp_1_limits=ConnectionLimits(1, 1),
                ),
            )
        )

        (beta_conn, beta_conn_tracker,) = await exit_stack.enter_async_context(
            new_connection_with_conn_tracker(
                client2_type,
                generate_connection_tracker_config(
                    client2_type,
                    derp_1_limits=ConnectionLimits(1, 1),
                ),
            )
        )

        alpha_client = await exit_stack.enter_async_context(
            telio.Client(
                alpha_conn,
                alpha,
                telio.AdapterType.BoringTun,
                telio_features=TelioFeatures(
                    direct=Direct(providers=endpoint_providers)
                ),
            ).run_meshnet(
                api.get_meshmap(alpha.id),
            )
        )

        beta_client_v3_6 = await exit_stack.enter_async_context(
            telio.Client(
                beta_conn,
                beta,
                telio.AdapterType.BoringTun,
                telio_features=TelioFeatures(
                    direct=Direct(providers=endpoint_providers)
                ),
            ).run_meshnet(api.get_meshmap(beta.id), True)
        )

        await testing.wait_long(
            asyncio.gather(
                alpha_client.wait_for_any_derp_state([telio.State.Connected]),
                beta_client_v3_6.wait_for_any_derp_state([telio.State.Connected]),
            ),
        )

        await testing.wait_long(
            asyncio.gather(
                alpha_conn_tracker.wait_for_event("derp_1"),
                beta_conn_tracker.wait_for_event("derp_1"),
            )
        )

        async with Ping(alpha_conn, beta.ip_addresses[0]).run() as ping:
            await testing.wait_long(ping.wait_for_next_ping())

        assert alpha_conn_tracker.get_out_of_limits() is None
        assert beta_conn_tracker.get_out_of_limits() is None
