"""Audited command ledger behind the legal remote-command gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .contracts import validate_contract_payload
from .governance import AuditLog
from .identity import new_id
from .legal_gate import FeatureGate, GatedFeature


class CommandType(str, Enum):
    SEND_MESSAGE = "send_message"
    LOCK_SCREEN = "lock_screen"
    FOCUS_POLICY = "focus_policy"
    REQUEST_CHECK_IN = "request_check_in"


class CommandAckStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Command:
    tenant_id: str
    command_id: str
    target_device_id: str
    command_type: CommandType
    requested_by: str
    requested_at: datetime
    payload: dict[str, Any]
    requires_legal_review: bool = True
    status: str = "queued"
    acknowledgements: list["CommandAck"] = field(default_factory=list)

    def contract_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "command_id": self.command_id,
            "target_device_id": self.target_device_id,
            "command_type": self.command_type.value,
            "requires_legal_review": self.requires_legal_review,
            "requested_by": self.requested_by,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class CommandAck:
    tenant_id: str
    command_id: str
    device_id: str
    status: CommandAckStatus
    acknowledged_at: datetime
    message: str = ""


class CommandLedger:
    """Stores command intent and acknowledgements, never executes commands."""

    def __init__(self, feature_gate: FeatureGate, audit_log: AuditLog) -> None:
        self.feature_gate = feature_gate
        self.audit_log = audit_log
        self.commands: dict[str, Command] = {}

    def create_command(
        self,
        tenant_id: str,
        target_device_id: str,
        command_type: CommandType,
        requested_by: str,
        payload: dict[str, Any],
        requested_at: datetime,
    ) -> Command:
        self.feature_gate.require_allowed(GatedFeature.REMOTE_COMMANDS, tenant_id=tenant_id)
        command = Command(
            tenant_id=tenant_id,
            command_id=new_id(),
            target_device_id=target_device_id,
            command_type=command_type,
            requested_by=requested_by,
            requested_at=requested_at,
            payload=dict(payload),
        )
        validate_contract_payload("command", command.contract_payload())
        self.commands[command.command_id] = command
        self.audit_log.record(
            tenant_id=tenant_id,
            actor_id=requested_by,
            action="command.create",
            target_type="device",
            target_id=target_device_id,
            occurred_at=requested_at,
            metadata={"command_id": command.command_id, "command_type": command_type.value},
        )
        return command

    def acknowledge(
        self,
        tenant_id: str,
        device_id: str,
        command_id: str,
        status: CommandAckStatus,
        acknowledged_at: datetime,
        message: str = "",
    ) -> CommandAck:
        command = self.commands[command_id]
        if command.tenant_id != tenant_id or command.target_device_id != device_id:
            raise PermissionError("Command acknowledgement is outside tenant/device scope")

        ack = CommandAck(
            tenant_id=tenant_id,
            command_id=command_id,
            device_id=device_id,
            status=status,
            acknowledged_at=acknowledged_at,
            message=message,
        )
        command.acknowledgements.append(ack)
        command.status = status.value
        self.audit_log.record(
            tenant_id=tenant_id,
            actor_id=device_id,
            action="command.ack",
            target_type="command",
            target_id=command_id,
            occurred_at=acknowledged_at,
            metadata={"status": status.value, "message": message},
        )
        return ack
