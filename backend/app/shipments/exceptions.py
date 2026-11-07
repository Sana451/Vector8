"""Shipment errors."""

from __future__ import annotations


class ShipmentError(Exception):
    pass


class ShipmentNotFoundError(ShipmentError):
    pass


class ShipmentAccessDeniedError(ShipmentError):
    pass


class ShipmentDocumentNotFoundError(ShipmentError):
    pass


class UnsupportedDocumentTypeError(ShipmentError):
    pass


class DocumentTooLargeError(ShipmentError):
    pass


class DocumentTextExtractionError(ShipmentError):
    """The PDF could not be read or has no usable text layer."""


class DocumentParsingError(ShipmentError):
    """The language model did not return usable structured data."""


class ShipmentNotPlannableError(ShipmentError):
    """The shipment lacks the geocoded stops a route needs."""
