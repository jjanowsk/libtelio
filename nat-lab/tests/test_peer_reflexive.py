from utils import Ping, stun
from contextlib import AsyncExitStack
from mesh_api import API
from config import DERP_PRIMARY, DERP_SECONDARY, DERP_TERTIARY, DERP_SERVERS
from telio import AdapterType, PathType
from telio_features import TelioFeatures, Direct
import asyncio
import pytest
import telio
import utils.testing as testing

from utils import (
    ConnectionTag,
    new_connection_by_tag,
)


@pytest.mark.asyncio
@pytest.mark.timeout(150)
async def test_peer_reflexive_endpoints() -> None:
    async with AsyncExitStack() as exit_stack:
        api = API()
        (alpha, beta) = api.default_config_two_nodes()

        alpha_connection = await exit_stack.enter_async_context(
            new_connection_by_tag(ConnectionTag.DOCKER_INTERNAL_SYMMETRIC_CLIENT)
        )

        beta_connection = await exit_stack.enter_async_context(
            new_connection_by_tag(ConnectionTag.DOCKER_SYMMETRIC_CLIENT_1)
        )

        alpha_client = await exit_stack.enter_async_context(
            telio.Client(
                alpha_connection,
                alpha,
                AdapterType.BoringTun,
                telio_features=TelioFeatures(direct=Direct(providers=["local"])),
            ).run_meshnet(
                api.get_meshmap(alpha.id),
            )
        )

        beta_client = await exit_stack.enter_async_context(
            telio.Client(
                beta_connection,
                beta,
                AdapterType.BoringTun,
                telio_features=TelioFeatures(direct=Direct(providers=["local"])),
            ).run_meshnet(
                api.get_meshmap(beta.id),
            )
        )

        # In this test we only want the clients to connect directly in this particular network setting
        await testing.wait_lengthy(
            asyncio.gather(
                alpha_client.handshake(
                    beta.public_key,
                    telio.PathType.Relay,
                ),
                beta_client.handshake(
                    alpha.public_key,
                    telio.PathType.Relay,
                ),
            ),
        )

        # In this test we only want the clients to connect directly in this particular network setting
        await testing.wait_lengthy(
            asyncio.gather(
                alpha_client.handshake(
                    beta.public_key,
                    telio.PathType.Direct,
                ),
                beta_client.handshake(
                    alpha.public_key,
                    telio.PathType.Direct,
                ),
            ),
        )

        async with Ping(alpha_connection, beta.ip_addresses[0]).run() as ping:
            await testing.wait_long(ping.wait_for_next_ping())

        async with Ping(beta_connection, alpha.ip_addresses[0]).run() as ping:
            await testing.wait_long(ping.wait_for_next_ping())
