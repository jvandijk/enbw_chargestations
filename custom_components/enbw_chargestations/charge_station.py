"""Charge station implementation."""

from abc import abstractmethod
from time import time
from typing import Any, override

import requests
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .utils import Utils

_LOGGER = logging.getLogger(__name__)


class ChargeStation:
    """Implementation for charge stations."""

    def __init__(
        self, hass: HomeAssistant, name: str, station_number: str, api_key: str
    ) -> None:
        """Initialize."""
        self.name: str = name
        self.hass: HomeAssistant = hass
        self.station_number: str = station_number
        self.api_key: str = api_key
        self.updated_at: float | None = None
        self.entities: list[ChargeStationEntity] = []
        self.unique_id: str = f"enbw_station_{station_number}"

    def update(self):
        """Update from rest api."""
        if self.updated_at is not None and self.updated_at > time() - 1000 * 60:
            return
        try:
            response = requests.get(
                f"https://enbw-emp.azure-api.net/emobility-public-api/api/v1/chargestations/{self.station_number}",
                headers={
                    "User-Agent": "Home Assistant",
                    "Ocp-Apim-Subscription-Key": self.api_key,
                    "Origin": "https://www.enbw.com",
                    "Referer": "https://www.enbw.com/",
                },
                timeout=1,
            ).json()
            if len(self.entities) == 0:
                self.create_entities(response)
            for i in range(len(self.entities)):
                entity: ChargePointEntity = self.entities[i]
                entity.update_from_response(response)

        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.exception(ex)
            return False
        self.updated_at = time()
        return True

    def create_entities(self, response):
        """Create and add entities to internal register."""
        self.entities.append(ChargeStationStateEntity(self.hass, self))
        self.entities.append(ChargePointCountEntity(self.hass, self))
        self.entities.append(ChargePointsAvailableEntity(self.hass, self))
        for i in range(response["numberOfChargePoints"]):
            point_id = response["chargePoints"][i]["evseId"]
            self.entities.append(ChargePointEntity(self.hass, self, point_id, i + 1))


class ChargeStationEntity(SensorEntity):
    """ChargeStationEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        self.hass: HomeAssistant = hass
        self.station: ChargeStation = station
        self._state: str | None = None

    def state(self):
        """State."""
        return self._state

    @abstractmethod
    def update_from_response(self, response):
        """Update from rest response."""

    def update(self):
        """Update complete station."""
        self.station.update()

    def update_state(self, state: str):
        """Update state."""
        self._state = state

    def update_attributes(self, attributes: dict[str, Any]):
        """Update attributes."""
        self.state_attributes = attributes


class ChargePointEntity(ChargeStationEntity):
    """ChargePointEntity implementation."""

    def __init__(
        self, hass: HomeAssistant, station: ChargeStation, point_id: str, index: int
    ) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self.index: int = index
        self.point_id: str = point_id
        self._attr_name = f"{station.name} Charge Point {self.index}"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_charge_point_{self.index}"
        )

    def update_from_response(self, response):
        """Update from rest response."""
        state = [x for x in response["chargePoints"] if x["evseId"] == self.point_id]
        if len(state) == 0:
            return
        state = state[0]
        self.update_state(state["status"])
        self.update_attributes({"plugTypeName": state["connectors"][0]["plugTypeName"]})


class ChargeStationStateEntity(ChargeStationEntity):
    """ChargeStationStateEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_name = f"{station.name}"
        self._attr_unique_id = Utils.generate_entity_id(f"{station.unique_id}_state")

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(
            "Available" if response["availableChargePoints"] > 0 else "Unavailable"
        )


class ChargePointsUnknownEntity(ChargeStationEntity):
    """ChargePointsUnknownEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_name = f"{station.name} Unknown State Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_unknown_state_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["unknownStateChargePoints"])


class ChargePointCountEntity(ChargeStationEntity):
    """ChargePointCountEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_name = f"{station.name} Total Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_total_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["numberOfChargePoints"])


class ChargePointsAvailableEntity(ChargeStationEntity):
    """ChargePointsAvailableEntity implementation."""

    def __init__(self, hass: HomeAssistant, station: ChargeStation) -> None:
        """Initialize."""
        super().__init__(hass, station)
        self._attr_name = f"{station.name} Available Charge Points"
        self._attr_unique_id = Utils.generate_entity_id(
            f"{station.unique_id}_available_charge_points"
        )

    @override
    def update_from_response(self, response):
        """Update from rest response."""
        self.update_state(response["availableChargePoints"])