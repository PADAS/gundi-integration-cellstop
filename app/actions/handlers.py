import datetime
import httpx
import json
import logging
import stamina
import app.actions.client as client

from app.services.state import IntegrationStateManager
from gundi_client_v2.client import GundiClient, GundiDataSenderClient


logger = logging.getLogger(__name__)


state_manager = IntegrationStateManager()


async def filter_and_transform(vehicles, integration_id, action_id):
    transformed_data = []
    main_data = ["deviceId", "name", "timeStr", "time", "y", "x"]
    for vehicle in vehicles:
        # Get current state for the device
        current_state = await state_manager.get_state(
            integration_id,
            action_id,
            vehicle.deviceId
        )

        if current_state:
            # Compare current state with new data
            latest_device_timestamp = datetime.datetime.strptime(
                current_state.get("latest_device_timestamp"),
                '%Y-%m-%d %H:%M:%S'
            )

            if vehicle.timeStr <= latest_device_timestamp:
                # Data is not new, not transform
                logger.info(
                    f"Excluding device ID '{vehicle.deviceId}' obs '{vehicle.timeStr}'"
                )
                continue

        data = {
            "source": vehicle.deviceId,
            "source_name": vehicle.name,
            'type': 'tracking-device',
            "recorded_at": vehicle.timeStr,
            "location": {
                "lat": vehicle.y,
                "lon": vehicle.x
            },
            "additional": {
                key: value for key, value in vehicle.dict().items()
                if key not in main_data and value is not None
            }
        }
        transformed_data.append(data)

        # Update state
        state = {
            "latest_device_timestamp": vehicle.timeStr
        }
        await state_manager.set_state(
            integration_id,
            action_id,
            state,
            vehicle.deviceId,
        )

    return transformed_data


async def action_auth(integration, action_config):
    logger.info(f"Executing auth action with integration {integration} and action_config {action_config}...")
    try:
        token = await client.get_auth_token(
            integration=integration,
            config=client.get_auth_config(integration)
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"valid_credentials": False}
        else:
            logger.error(f"Error getting token from Cellstop API. status code: {e.response.status_code}")
            raise e
    except httpx.HTTPError as e:
        message = f"auth action returned error."
        logger.exception(message, extra={
            "integration_id": str(integration.id),
            "attention_needed": True
        })
        raise e
    else:
        logger.info(f"Authenticated with success. token: {token}")
        return {"valid_credentials": token is not None}


async def action_fetch_samples(integration, action_config):
    logger.info(f"Executing fetch_samples action with integration {integration} and action_config {action_config}...")
    try:
        vehicles = await client.get_vehicles_positions(
            integration=integration,
            config=client.get_fetch_samples_config(integration)
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            message = f"Invalid credentials. Please review the integration configuration. Integration id: {integration.id}"
            logger.warning(message, extra={"integration_id": str(integration.id)})
            return {
                "observations_extracted": 0,
                "observations": [],
                "error": "Invalid credentials. Please review the authentication configuration."
            }
        else:
            logger.error(f"Error getting token from Cellstop API. status code: {e.response.status_code}")
            raise e
    except httpx.HTTPError as e:
        message = f"fetch_samples action returned error."
        logger.exception(message, extra={
            "integration_id": str(integration.id),
            "attention_needed": True
        })
        raise e
    else:
        logger.info(f"Observations pulled with success.")
        return {
            "observations_extracted": len(vehicles),
            "observations": [json.loads(vehicle.json()) for vehicle in vehicles]
        }


async def action_pull_observations(integration, action_config):
    logger.info(f"Executing pull_observations action with integration {integration} and action_config {action_config}...")
    try:
        async for attempt in stamina.retry_context(
                on=httpx.HTTPError,
                attempts=3,
                wait_initial=datetime.timedelta(seconds=10),
                wait_max=datetime.timedelta(seconds=10),
        ):
            with attempt:
                vehicles = await client.get_vehicles_positions(
                    integration=integration,
                    config=client.get_pull_config(integration)
                )

        logger.info(f"Observations pulled with success.")

        transformed_data = await filter_and_transform(
            vehicles,
            str(integration.id),
            action_config.action.value
        )

        if transformed_data:
            # Send transformed data to Sensors API V2 (within gundi-client)
            gundi_client = GundiClient()
            async for attempt in stamina.retry_context(
                    on=httpx.HTTPError,
                    attempts=3,
                    wait_initial=datetime.timedelta(seconds=10),
                    wait_max=datetime.timedelta(seconds=10),
            ):
                with attempt:
                    apikey = await gundi_client.get_integration_api_key(
                        integration_id=str(integration.id)
                    )

            data_sender_client = GundiDataSenderClient(
                integration_api_key=apikey
            )
            async for attempt in stamina.retry_context(
                    on=httpx.HTTPError,
                    attempts=3,
                    wait_initial=datetime.timedelta(seconds=10),
                    wait_max=datetime.timedelta(seconds=10),
            ):
                with attempt:
                    response = await data_sender_client.post_observations(
                        data=transformed_data
                    )
        else:
            response = []
    except httpx.HTTPError as e:
        message = f"pull_observations action returned error."
        logger.exception(message, extra={
            "integration_id": str(integration.id),
            "attention_needed": True
        })
        raise e
    else:
        return response
