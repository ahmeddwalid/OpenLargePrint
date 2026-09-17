"""Sidecar IPC package for desktop shell integration (DESIGN.md §9, SEC-005)."""

from openlargeprint.sidecar.protocol import (
    CancelledEvent,
    CheckpointEvent,
    CommandType,
    ConvertCommand,
    ErrorEvent,
    EventType,
    HealthCheckCommand,
    HealthCheckEvent,
    InspectCommand,
    InspectResultEvent,
    ProgressEvent,
    ReviewDataEvent,
    SuccessEvent,
)
from openlargeprint.sidecar.runner import SidecarRunner

__all__ = [
    "SidecarRunner",
    "CommandType",
    "EventType",
    "HealthCheckCommand",
    "InspectCommand",
    "ConvertCommand",
    "HealthCheckEvent",
    "InspectResultEvent",
    "ProgressEvent",
    "CheckpointEvent",
    "ReviewDataEvent",
    "SuccessEvent",
    "CancelledEvent",
    "ErrorEvent",
]
